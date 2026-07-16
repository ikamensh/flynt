//! Port of src/flynt/transform/percent_transformer.py.
//! Owner: task #5 (percent pipeline).
//!
//! Converts a `left % right` `BinOp` whose left operand is a literal string
//! into the f-string equivalent (a ruff `ExprFString`, i.e. CPython's
//! `ast.JoinedStr`). The `%`-format grammar is parsed by the hand-written
//! scanners below, which faithfully reproduce flynt's `re` patterns
//! (`VAR_KEY_PATTERN`, `DICT_PATTERN`, `SPLIT_DICT_PATTERN`, `ANY_DICT`),
//! including their quirks (no negative lookbehind on `VAR_KEY_PATTERN` /
//! `DICT_PATTERN`, so `%%` can be re-interpreted as a conversion).

use std::collections::HashMap;

use ruff_python_ast::name::Name;
use ruff_python_ast::{
    Arguments, AtomicNodeIndex, Expr, ExprCall, ExprContext, ExprName, ExprSubscript,
    InterpolatedStringElement, Operator,
};
use ruff_text_size::TextRange;

use crate::astutils::{
    ast_formatted_value, ast_string_node, get_str_value, is_str_constant, new_joined_str,
    new_string_literal,
};
use crate::error::FlyntError;
use crate::state::State;

/// Conversion characters accepted after an optional `[hlL]` length modifier.
/// Mirrors `FORMATS = "diouxXeEfFgGcrsa"`.
const FORMATS: &str = "diouxXeEfFgGcrsa";
/// `integer_specificers = "dxXob"` — the specifiers for which a `.` in the
/// prefix is rewritten to `0`. (`b` is unreachable from the input regex.)
const INTEGER_SPECIFIERS: &str = "dxXob";

// --- public API ------------------------------------------------------------

/// Port of `is_percent_stringify`: the transformer-level eligibility guard.
/// Narrower than candidate discovery — in addition to a literal-string left
/// operand under `%`, the right operand must be one of `Tuple`, `List`, `Dict`,
/// or a `supported_operand` (`Name`, `Attribute`, `Constant`, `Subscript`,
/// `Call`, `BinOp`, `IfExp`).
pub fn is_percent_stringify(node: &Expr) -> bool {
    let Expr::BinOp(b) = node else {
        return false;
    };
    matches!(b.op, Operator::Mod) && is_str_constant(&b.left) && is_supported_rhs(&b.right)
}

/// `Tuple`/`List`/`Dict` plus the `supported_operands` set.
fn is_supported_rhs(right: &Expr) -> bool {
    matches!(
        right,
        Expr::Tuple(_) | Expr::List(_) | Expr::Dict(_) | // container RHS
        Expr::Name(_)
            | Expr::Attribute(_)
            | Expr::Subscript(_)
            | Expr::Call(_)
            | Expr::BinOp(_)
            | Expr::If(_)
            // ast.Constant covers every ruff literal variant:
            | Expr::StringLiteral(_)
            | Expr::BytesLiteral(_)
            | Expr::NumberLiteral(_)
            | Expr::BooleanLiteral(_)
            | Expr::NoneLiteral(_)
            | Expr::EllipsisLiteral(_)
    )
}

/// Port of `transform_binop`: convert `left % right` into a JoinedStr f-string
/// expression. `state.aggressive` supplies the aggressive level.
pub fn transform_binop(node: &Expr, state: &State) -> Result<Expr, FlyntError> {
    let aggressive = state.aggressive;
    let Expr::BinOp(binop) = node else {
        return Err(FlyntError::ConversionRefused(
            "transform_binop called on a non-BinOp node".to_string(),
        ));
    };
    let left_str = get_str_value(&binop.left)?;
    let right = binop.right.as_ref();

    let segments = match right {
        // supported_operands (Name/Attribute/Constant/Subscript/Call/BinOp/IfExp)
        // -> transform_generic, which sniffs for a mapping style before falling
        // back to a synthetic one-element tuple.
        Expr::Name(_)
        | Expr::Attribute(_)
        | Expr::Subscript(_)
        | Expr::Call(_)
        | Expr::BinOp(_)
        | Expr::If(_)
        | Expr::StringLiteral(_)
        | Expr::BytesLiteral(_)
        | Expr::NumberLiteral(_)
        | Expr::BooleanLiteral(_)
        | Expr::NoneLiteral(_)
        | Expr::EllipsisLiteral(_) => transform_generic(&left_str, right, aggressive)?,

        Expr::Tuple(t) => transform_tuple(&left_str, &t.elts, aggressive)?,
        // A list RHS is treated exactly like a tuple.
        Expr::List(l) => transform_tuple(&left_str, &l.elts, aggressive)?,
        Expr::Dict(_) => transform_dict(&left_str, right, aggressive)?,

        other => {
            return Err(FlyntError::ConversionRefused(format!(
                "Unsupported `node.right` class: <class 'ast.{}'>",
                cpython_ast_name(other)
            )));
        }
    };

    Ok(new_joined_str(segments))
}

// --- transform_tuple / transform_generic / transform_dict ------------------

/// Port of `transform_tuple` (also used by `transform_list` and the
/// single-value branch of `transform_generic`). `elts` are the tuple/list
/// elements paired strictly left-to-right with `VAR_KEY_PATTERN` matches.
fn transform_tuple(
    left_str: &str,
    elts: &[Expr],
    aggressive: u8,
) -> Result<Vec<InterpolatedStringElement>, FlyntError> {
    let cs: Vec<char> = left_str.chars().collect();
    let matches = scan_var_key(&cs);
    if elts.len() != matches.len() {
        return Err(FlyntError::ConversionRefused(
            "This expression involves tuple unpacking.".to_string(),
        ));
    }

    let mut segments: Vec<InterpolatedStringElement> = Vec::new();
    let mut pos = 0usize;
    for (idx, m) in matches.iter().enumerate() {
        segments.push(literal_segment(&cs[pos..m.start]));
        let fv = formatted_value(&m.prefix, m.conv, elts[idx].clone(), aggressive)?;
        segments.push(fv);
        pos = m.end;
    }
    segments.push(literal_segment(&cs[pos..]));
    Ok(segments)
}

/// Port of `transform_generic`: if the format string contains any `DICT_PATTERN`
/// placeholder, switch to mapping mode; otherwise wrap the RHS in a synthetic
/// one-element tuple.
fn transform_generic(
    left_str: &str,
    right: &Expr,
    aggressive: u8,
) -> Result<Vec<InterpolatedStringElement>, FlyntError> {
    let cs: Vec<char> = left_str.chars().collect();
    if !scan_dict(&cs).is_empty() {
        return transform_dict(left_str, right, aggressive);
    }
    transform_tuple(left_str, std::slice::from_ref(right), aggressive)
}

/// Port of `transform_dict`: mapping-style `%(key)spec` formatting. For a
/// literal `ast.Dict` RHS the keys are resolved against the dict literal
/// (non-aggressive removes a key on use, so reuse is a hard error); for any
/// other RHS each placeholder becomes a fresh `rhs['key']` subscript.
fn transform_dict(
    left_str: &str,
    right: &Expr,
    aggressive: u8,
) -> Result<Vec<InterpolatedStringElement>, FlyntError> {
    let cs: Vec<char> = left_str.chars().collect();
    let matches = scan_dict(&cs);
    if matches.len() != count_any_dict(&cs) {
        return Err(FlyntError::ConversionRefused(
            "Some locations have unknown format modifiers.".to_string(),
        ));
    }

    // Build a key -> value map for a literal dict RHS.
    let mut lit_map: Option<HashMap<String, Expr>> = None;
    if let Expr::Dict(d) = right {
        let mut map = HashMap::new();
        for item in &d.items {
            // `**mapping` unpacking yields a `None` key; skip it (Python:
            // `if k is not None`).
            if let Some(key_node) = &item.key {
                map.insert(literal_eval_key(key_node)?, item.value.clone());
            }
        }
        lit_map = Some(map);
    }

    let mut segments: Vec<InterpolatedStringElement> = Vec::new();
    let mut pos = 0usize;
    for m in &matches {
        segments.push(literal_segment(&cs[pos..m.start]));

        if m.key.is_empty() {
            // The scanner requires >= 1 key char, so this is unreachable, but
            // matches the Python `FlyntException("could not find dict key")`.
            return Err(FlyntError::Generic("could not find dict key".to_string()));
        }

        let val = match &mut lit_map {
            Some(map) => {
                let looked_up = if aggressive >= 1 {
                    map.get(&m.key).cloned()
                } else {
                    // Non-aggressive: pop, so a repeated key raises KeyError and
                    // the whole candidate is skipped upstream.
                    map.remove(&m.key)
                };
                looked_up
                    .ok_or_else(|| FlyntError::Generic(format!("KeyError: '{}'", m.key)))?
            }
            None => make_subscript(right, &m.key),
        };

        let fv = formatted_value(&m.prefix, m.conv, val, aggressive)?;
        segments.push(fv);
        pos = m.end;
    }
    segments.push(literal_segment(&cs[pos..]));
    Ok(segments)
}

// --- formatted_value -------------------------------------------------------

/// Port of `formatted_value`: turn one placeholder `(prefix, conv)` plus its
/// value expression into an f-string element, applying the conversion table and
/// the aggressive-mode `%d`/alignment rules.
fn formatted_value(
    prefix: &str,
    conv: char,
    val: Expr,
    aggressive: u8,
) -> Result<InterpolatedStringElement, FlyntError> {
    // The `.`-to-`0` rewrite happens *before* i/u are translated to d, so it
    // applies to an original d/o/x/X but not to an original i/u.
    let mut prefix = prefix.to_string();
    if INTEGER_SPECIFIERS.contains(conv) {
        prefix = prefix.replace('.', "0");
    }

    // conversion_methods: r -> !r, a -> !a, s -> (no flag).
    if conv == 'r' || conv == 'a' || conv == 's' {
        let conv_method: Option<&str> = match conv {
            'r' => Some("!r"),
            'a' => Some("!a"),
            _ => None,
        };

        if conv == 's' && !prefix.is_empty() {
            if let Some(rest) = prefix.strip_prefix('-') {
                // Leading `-` => left alignment; drop it, keep the rest.
                return ast_formatted_value(val, Some(rest), conv_method);
            }
            if aggressive >= 1 {
                // Right alignment made explicit.
                let fs = format!(">{prefix}");
                return ast_formatted_value(val, Some(&fs), conv_method);
            }
        }

        if aggressive < 1 && !prefix.is_empty() {
            return Err(FlyntError::ConversionRefused(
                "Default text alignment has changed between percent fmt and fstrings. \
                 Proceeding would result in changed code behaviour."
                    .to_string(),
            ));
        }
        return ast_formatted_value(val, Some(&prefix), conv_method);
    }

    // translate_conversion_types: i, u -> d.
    let conv = match conv {
        'i' | 'u' => 'd',
        other => other,
    };

    if conv == 'd' {
        let mut val = val;
        if !is_builtin_int_call(&val) {
            if aggressive < 1 {
                return Err(FlyntError::ConversionRefused(
                    "Skipping %d formatting - fstrings behave differently from % formatting."
                        .to_string(),
                ));
            }
            if aggressive < 2 {
                val = wrap_int_call(val);
            }
        }
        // The explicit `d` type is removed: fmt_str = prefix + "".
        return ast_formatted_value(val, Some(&prefix), None);
    }

    // e/E/f/F/g/G/c: append the type after the prefix.
    let fs = format!("{prefix}{conv}");
    ast_formatted_value(val, Some(&fs), None)
}

/// Port of `_is_builtin_int_call`: a direct `int(...)` or `len(...)` call.
/// Recognized purely by the bare callee name (which may be shadowed — see the
/// SPEC quirk).
fn is_builtin_int_call(val: &Expr) -> bool {
    if let Expr::Call(c) = val {
        if let Expr::Name(n) = c.func.as_ref() {
            let id = n.id.as_str();
            return id == "int" || id == "len";
        }
    }
    false
}

/// Build `int(val)` (`ast.Call(func=Name("int"), args=[val], keywords=[])`).
fn wrap_int_call(val: Expr) -> Expr {
    Expr::Call(ExprCall {
        node_index: AtomicNodeIndex::default(),
        range: TextRange::default(),
        func: Box::new(Expr::Name(ExprName {
            node_index: AtomicNodeIndex::default(),
            range: TextRange::default(),
            id: Name::new("int"),
            ctx: ExprContext::Load,
        })),
        arguments: Arguments {
            range: TextRange::default(),
            node_index: AtomicNodeIndex::default(),
            args: Box::from([val]),
            keywords: Box::from([]),
        },
    })
}

/// Build `value['key']` (`ast.Subscript(value, slice=Constant(key))`).
fn make_subscript(value: &Expr, key: &str) -> Expr {
    Expr::Subscript(ExprSubscript {
        node_index: AtomicNodeIndex::default(),
        range: TextRange::default(),
        value: Box::new(value.clone()),
        slice: Box::new(new_string_literal(key)),
        ctx: ExprContext::Load,
    })
}

/// `str(ast.literal_eval(key_node))` for a literal dict key. Realistic mapping
/// keys are strings; ints/bools/None are supported for completeness. Anything
/// else (a non-literal key, a float/complex) is an ordinary error, mirroring
/// `ast.literal_eval` raising `ValueError` (caught upstream, not a
/// `ConversionRefused`).
fn literal_eval_key(key_node: &Expr) -> Result<String, FlyntError> {
    match key_node {
        Expr::StringLiteral(s) => Ok(s.value.to_str().to_string()),
        Expr::BooleanLiteral(b) => Ok(if b.value { "True" } else { "False" }.to_string()),
        Expr::NoneLiteral(_) => Ok("None".to_string()),
        Expr::NumberLiteral(num) => match &num.value {
            ruff_python_ast::Number::Int(i) => Ok(i.to_string()),
            _ => Err(FlyntError::Generic(
                "malformed node or string: non-integer dict key".to_string(),
            )),
        },
        _ => Err(FlyntError::Generic(
            "malformed node or string: non-literal dict key".to_string(),
        )),
    }
}

/// A literal block turned into an f-string literal element, applying `%% -> %`.
fn literal_segment(chars: &[char]) -> InterpolatedStringElement {
    let raw: String = chars.iter().collect();
    ast_string_node(&raw.replace("%%", "%"))
}

/// CPython `ast` node class name for `type(node.right).__name__`, used to
/// reproduce the unsupported-RHS refusal text (`<class 'ast.Set'>`). Only the
/// variants that can actually reach the unsupported branch matter; the
/// container/operand variants handled earlier are included for completeness.
fn cpython_ast_name(expr: &Expr) -> &'static str {
    match expr {
        Expr::BoolOp(_) => "BoolOp",
        Expr::Named(_) => "NamedExpr",
        Expr::BinOp(_) => "BinOp",
        Expr::UnaryOp(_) => "UnaryOp",
        Expr::Lambda(_) => "Lambda",
        Expr::If(_) => "IfExp",
        Expr::Dict(_) => "Dict",
        Expr::Set(_) => "Set",
        Expr::ListComp(_) => "ListComp",
        Expr::SetComp(_) => "SetComp",
        Expr::DictComp(_) => "DictComp",
        Expr::Generator(_) => "GeneratorExp",
        Expr::Await(_) => "Await",
        Expr::Yield(_) => "Yield",
        Expr::YieldFrom(_) => "YieldFrom",
        Expr::Compare(_) => "Compare",
        Expr::Call(_) => "Call",
        Expr::FString(_) => "JoinedStr",
        Expr::StringLiteral(_)
        | Expr::BytesLiteral(_)
        | Expr::NumberLiteral(_)
        | Expr::BooleanLiteral(_)
        | Expr::NoneLiteral(_)
        | Expr::EllipsisLiteral(_) => "Constant",
        Expr::Attribute(_) => "Attribute",
        Expr::Subscript(_) => "Subscript",
        Expr::Starred(_) => "Starred",
        Expr::Name(_) => "Name",
        Expr::List(_) => "List",
        Expr::Tuple(_) => "Tuple",
        Expr::Slice(_) => "Slice",
        // ruff-only variants with no CPython `ast` counterpart.
        Expr::TString(_) => "TemplateStr",
        Expr::IpyEscapeCommand(_) => "IpyEscapeCommand",
    }
}

// --- %-format scanners (faithful ports of the `re` patterns) ---------------

/// One `VAR_KEY_PATTERN` match: the byte-independent char span `[start, end)`
/// plus the captured `prefix` and conversion char.
struct VarKeyMatch {
    start: usize,
    end: usize,
    prefix: String,
    conv: char,
}

/// Try to match `%([+-]?[0-9]*[.]?[0-9]*)[hlL]?([diouxXeEfFgGcrsa])` anchored at
/// `i`. The char classes involved are disjoint, so greedy matching is
/// deterministic (no backtracking needed).
fn match_var_key_at(cs: &[char], i: usize) -> Option<VarKeyMatch> {
    let n = cs.len();
    if i >= n || cs[i] != '%' {
        return None;
    }
    let mut p = i + 1;
    let prefix_start = p;
    consume_prefix(cs, &mut p);
    let prefix: String = cs[prefix_start..p].iter().collect();
    consume_length_modifier(cs, &mut p);
    if p < n && FORMATS.contains(cs[p]) {
        return Some(VarKeyMatch {
            start: i,
            end: p + 1,
            prefix,
            conv: cs[p],
        });
    }
    None
}

/// All non-overlapping `VAR_KEY_PATTERN` matches, left to right. Reproduces
/// `re.findall`/`re.split` scanning: try to match at each position; on a match,
/// resume at its end; otherwise advance by one. (No negative lookbehind, so a
/// `%` inside `%%` can be re-interpreted as a conversion.)
fn scan_var_key(cs: &[char]) -> Vec<VarKeyMatch> {
    let mut out = Vec::new();
    let mut i = 0;
    while i < cs.len() {
        if let Some(m) = match_var_key_at(cs, i) {
            i = m.end;
            out.push(m);
        } else {
            i += 1;
        }
    }
    out
}

/// One `DICT_PATTERN` match: span plus captured key, prefix, conversion char.
struct DictMatch {
    start: usize,
    end: usize,
    key: String,
    prefix: String,
    conv: char,
}

/// Match `%\(([^)]+)\)([+-]?[0-9]*[.]?[0-9]*)[hlL]?([diouxXeEfFgGcrsa])`
/// anchored at `i` (the `SPLIT_DICT_PATTERN` grouping, wrapped by `DICT_PATTERN`
/// as one group covering the whole placeholder).
fn match_dict_at(cs: &[char], i: usize) -> Option<DictMatch> {
    let n = cs.len();
    if i + 1 >= n || cs[i] != '%' || cs[i + 1] != '(' {
        return None;
    }
    let mut p = i + 2;
    let key_start = p;
    while p < n && cs[p] != ')' {
        p += 1;
    }
    if p == key_start || p >= n {
        // empty key ([^)]+ needs >= 1) or missing closing ')'
        return None;
    }
    let key: String = cs[key_start..p].iter().collect();
    p += 1; // consume ')'
    let prefix_start = p;
    consume_prefix(cs, &mut p);
    let prefix: String = cs[prefix_start..p].iter().collect();
    consume_length_modifier(cs, &mut p);
    if p < n && FORMATS.contains(cs[p]) {
        return Some(DictMatch {
            start: i,
            end: p + 1,
            key,
            prefix,
            conv: cs[p],
        });
    }
    None
}

/// All non-overlapping `DICT_PATTERN` matches, left to right.
fn scan_dict(cs: &[char]) -> Vec<DictMatch> {
    let mut out = Vec::new();
    let mut i = 0;
    while i < cs.len() {
        if let Some(m) = match_dict_at(cs, i) {
            i = m.end;
            out.push(m);
        } else {
            i += 1;
        }
    }
    out
}

/// Count `ANY_DICT = (?<!%)%\([^)]+?\)` matches: a `%(...)` not immediately
/// preceded by another `%`. Used only for the count-mismatch refusal.
fn count_any_dict(cs: &[char]) -> usize {
    let n = cs.len();
    let mut count = 0;
    let mut i = 0;
    while i < n {
        if cs[i] == '%'
            && (i == 0 || cs[i - 1] != '%') // negative lookbehind
            && i + 1 < n
            && cs[i + 1] == '('
        {
            let mut p = i + 2;
            let key_start = p;
            while p < n && cs[p] != ')' {
                p += 1;
            }
            if p > key_start && p < n && cs[p] == ')' {
                count += 1;
                i = p + 1;
                continue;
            }
        }
        i += 1;
    }
    count
}

/// Consume `[+-]?[0-9]*[.]?[0-9]*` (the `PREFIX_GROUP`) starting at `*p`.
fn consume_prefix(cs: &[char], p: &mut usize) {
    let n = cs.len();
    if *p < n && (cs[*p] == '+' || cs[*p] == '-') {
        *p += 1;
    }
    while *p < n && cs[*p].is_ascii_digit() {
        *p += 1;
    }
    if *p < n && cs[*p] == '.' {
        *p += 1;
    }
    while *p < n && cs[*p].is_ascii_digit() {
        *p += 1;
    }
}

/// Consume an optional `[hlL]` length modifier (discarded).
fn consume_length_modifier(cs: &[char], p: &mut usize) {
    if *p < cs.len() && matches!(cs[*p], 'h' | 'l' | 'L') {
        *p += 1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::astutils::{fixup_transformed, parse_expr};

    /// Transform `src` at the given aggressive level and render to final source
    /// via `fixup_transformed` (the byte-for-byte contract vs. Python).
    fn tf(src: &str, aggressive: u8) -> Result<String, FlyntError> {
        let node = parse_expr(src).unwrap();
        let mut state = State::default();
        state.aggressive = aggressive;
        let result = transform_binop(&node, &state)?;
        fixup_transformed(result, None)
    }

    fn ok(src: &str, aggressive: u8) -> String {
        tf(src, aggressive).unwrap()
    }

    #[test]
    fn basic_tuple_list_generic() {
        assert_eq!(ok("'%s' % x", 0), "f\"{x}\"");
        assert_eq!(ok("'%s and %s' % (a, b)", 0), "f\"{a} and {b}\"");
        assert_eq!(ok("'%s and %s' % [a, b]", 0), "f\"{a} and {b}\"");
        assert_eq!(ok("'application \"%s\"' % obj.name", 0), "f\"application \\\"{obj.name}\\\"\"");
    }

    #[test]
    fn percent_d_rules() {
        // aggressive 0 refuses a bare value; int()/len() are always accepted.
        assert!(matches!(
            tf("'%d' % x", 0),
            Err(FlyntError::ConversionRefused(_))
        ));
        assert_eq!(ok("'%d' % x", 1), "f\"{int(x)}\"");
        assert_eq!(ok("'%d' % x", 2), "f\"{x}\"");
        assert_eq!(ok("'%d' % int(x)", 0), "f\"{int(x)}\"");
        assert_eq!(ok("'%d' % len(x)", 0), "f\"{len(x)}\"");
        assert_eq!(ok("'%i' % x", 1), "f\"{int(x)}\"");
    }

    #[test]
    fn numeric_types_and_prefix() {
        assert_eq!(ok("'%03X' % x", 0), "f\"{x:03X}\"");
        assert_eq!(ok("'%.03f' % x", 0), "f\"{x:.03f}\"");
        assert_eq!(ok("'%f' % x", 0), "f\"{x:f}\"");
        // integer specifier: `.` in prefix rewritten to `0`.
        assert_eq!(ok("'%.3x' % x", 0), "f\"{x:03x}\"");
    }

    #[test]
    fn conversions_r_a_s() {
        assert_eq!(ok("'%r' % x", 0), "f\"{x!r}\"");
        assert_eq!(ok("'%a' % x", 0), "f\"{x!a}\"");
        // %s alignment rules
        assert_eq!(ok("'%-5s' % x", 0), "f\"{x:5}\"");
        assert_eq!(ok("'%5s' % x", 1), "f\"{x:>5}\"");
        assert!(matches!(
            tf("'%5s' % x", 0),
            Err(FlyntError::ConversionRefused(_))
        ));
        // %r/%a with prefix: refuse at 0, keep prefix without `>` at 1+.
        assert!(matches!(
            tf("'%20r' % x", 0),
            Err(FlyntError::ConversionRefused(_))
        ));
        assert_eq!(ok("'%20r' % x", 1), "f\"{x!r:20}\"");
    }

    #[test]
    fn mapping_dict_and_generic() {
        assert_eq!(ok("'val: %(k)s' % d", 0), "f\"val: {d['k']}\"");
        assert_eq!(
            ok("'val: %(k)s more %(j)d' % d", 1),
            "f\"val: {d['k']} more {int(d['j'])}\""
        );
        assert_eq!(ok("'%(k)s' % {'k': v}", 0), "f\"{v}\"");
        // literal dict reuse: refused (KeyError) at 0, allowed at 1.
        assert!(tf("'%(k)s %(k)s' % {'k': v}", 0).is_err());
        assert_eq!(ok("'%(k)s %(k)s' % {'k': v}", 1), "f\"{v} {v}\"");
    }

    #[test]
    fn literal_percent_and_quirks() {
        assert_eq!(ok("'100%% done %s' % x", 0), "f\"100% done {x}\"");
        // %% quirk: no lookbehind, so `%d` inside `%%d` is a conversion.
        assert_eq!(ok("'%%d' % (x,)", 1), "f\"%{int(x)}\"");
    }

    #[test]
    fn refusals() {
        // tuple arity mismatch
        assert!(matches!(
            tf("'%s %s' % (a,)", 0),
            Err(FlyntError::ConversionRefused(_))
        ));
        // unknown modifier in mapping -> tuple path -> unpacking refusal
        assert!(matches!(
            tf("'%(k)z' % d", 0),
            Err(FlyntError::ConversionRefused(_))
        ));
        // unsupported RHS (Set)
        assert!(matches!(
            tf("'%s' % {x}", 0),
            Err(FlyntError::ConversionRefused(_))
        ));
    }

    #[test]
    fn is_percent_stringify_guard() {
        assert!(is_percent_stringify(&parse_expr("'%s' % x").unwrap()));
        assert!(is_percent_stringify(&parse_expr("'%s' % (a, b)").unwrap()));
        assert!(is_percent_stringify(&parse_expr("'%(k)s' % {'k': v}").unwrap()));
        // Set RHS is not eligible.
        assert!(!is_percent_stringify(&parse_expr("'%s' % {x}").unwrap()));
        // non-% operator / non-literal left
        assert!(!is_percent_stringify(&parse_expr("'a' + x").unwrap()));
        assert!(!is_percent_stringify(&parse_expr("var % x").unwrap()));
    }
}
