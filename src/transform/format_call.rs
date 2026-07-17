//! Port of src/flynt/transform/format_call_transforms.py (`joined_string`).
//! Owner: task #6 (.format() pipeline).
//!
//! Converts a `"...".format(...)` call node into an f-string (or a plain string
//! constant when every produced segment is literal). Field selection, attribute
//! suffixes, nested format specs, and the non-aggressive reuse/unused checks all
//! mirror the Python original.

use std::collections::HashMap;

use ruff_python_ast::visitor::{walk_expr, Visitor};
use ruff_python_ast::{
    AtomicNodeIndex, Expr, ExprAttribute, ExprContext, FStringPart, Identifier,
    InterpolatedStringElement,
};
use ruff_text_size::TextRange;

use crate::astutils::{
    ast_formatted_value_with_nested, ast_string_node, get_str_value, is_str_constant,
    new_joined_str, new_string_literal, stdlib_parse, FieldKey,
};
use crate::error::FlyntError;

/// Port of `joined_string`. `aggressive` corresponds to `state.aggressive >= 1`.
pub fn joined_string(fmt_call: &Expr, aggressive: bool) -> Result<Expr, FlyntError> {
    let call = match fmt_call {
        Expr::Call(c) => c,
        _ => return Err(only_literal()),
    };
    let receiver = match call.func.as_ref() {
        Expr::Attribute(attr) if is_str_constant(&attr.value) => attr.value.as_ref(),
        _ => return Err(only_literal()),
    };
    let format_str = get_str_value(receiver)?;

    // var_map: keyword args by name, then positional args by index. A bare
    // `**kwargs` (keyword with no name) has no key it could ever satisfy; track
    // it so the non-aggressive "never used" check below still fires.
    let mut var_map: HashMap<FieldKey, Expr> = HashMap::new();
    let mut has_double_star = false;
    for kw in call.arguments.keywords.iter() {
        match &kw.arg {
            Some(name) => {
                var_map.insert(FieldKey::Name(name.as_str().to_string()), kw.value.clone());
            }
            None => has_double_star = true,
        }
    }

    // Refuse any inserted string/bytes constant that would need a backslash in an
    // f-string expression part (newline/tab/CR/backslash, or a lone quote char).
    for arg in call.arguments.args.iter() {
        check_no_backslash(arg)?;
    }
    for kw in call.arguments.keywords.iter() {
        check_no_backslash(&kw.value)?;
    }

    for (i, val) in call.arguments.args.iter().enumerate() {
        var_map.insert(FieldKey::Index(i), val.clone());
    }

    // `stdlib_parse` (the astutils port of `string.Formatter().parse`) does not
    // reproduce CPython's brace-validation errors, so an invalid format string
    // (e.g. a lone `{` or `}`) would otherwise be silently transformed. Reject
    // exactly the strings CPython's `Formatter.parse` raises `ValueError` on.
    validate_format_string(&format_str)?;

    let mut seq_ctr: usize = 0;
    let mut manual_field_ordering = false;
    let mut new_segments: Vec<InterpolatedStringElement> = Vec::new();

    for field in stdlib_parse(&format_str) {
        if !field.literal.is_empty() {
            new_segments.push(ast_string_node(&field.literal));
        }
        let var_name = match field.field_name {
            Some(v) => v,
            None => continue,
        };

        if var_name.contains('[') {
            return Err(FlyntError::Generic(format!(
                "Skipping f-stringify of a fmt call with indexed name {var_name}"
            )));
        }

        // A `.` splits the base argument selector from a single attribute suffix
        // (the whole remainder becomes one `attr`, matching Python's quirk).
        let (base_name, suffix) = match var_name.find('.') {
            Some(idx) => (var_name[..idx].to_string(), var_name[idx + 1..].to_string()),
            None => (var_name, String::new()),
        };

        let key = if !base_name.is_empty() && base_name.chars().all(|c| c.is_ascii_digit()) {
            manual_field_ordering = true;
            FieldKey::Index(
                base_name
                    .parse()
                    .map_err(|_| FlyntError::Generic("invalid field index".into()))?,
            )
        } else if base_name.is_empty() {
            if manual_field_ordering {
                // Python `assert not manual_field_ordering` (AssertionError ->
                // caught -> chunk skipped).
                return Err(FlyntError::Generic(
                    "cannot switch from manual field numbering to automatic".into(),
                ));
            }
            let k = FieldKey::Index(seq_ctr);
            seq_ctr += 1;
            k
        } else {
            FieldKey::Name(base_name)
        };

        let mut selected = if aggressive {
            var_map
                .get(&key)
                .cloned()
                .ok_or_else(|| FlyntError::Generic(format!("missing argument for {key:?}")))?
        } else {
            var_map.remove(&key).ok_or_else(|| {
                FlyntError::ConversionRefused(format!(
                    "A variable {} is used multiple times - better not to replace it.",
                    key_display(&key)
                ))
            })?
        };

        if !suffix.is_empty() {
            selected = Expr::Attribute(ExprAttribute {
                node_index: AtomicNodeIndex::default(),
                range: TextRange::default(),
                value: Box::new(selected),
                attr: Identifier::new(suffix, TextRange::default()),
                ctx: ExprContext::Load,
            });
        }

        // Only `!s`, `!r`, `!a` are valid; anything else would make `ast.unparse`
        // raise "Unknown f-string conversion" in Python, so refuse the chunk.
        let conversion = match field.conversion {
            Some(c @ ('s' | 'r' | 'a')) => Some(c.to_string()),
            Some(_) => {
                return Err(FlyntError::ConversionRefused(
                    "Unknown f-string conversion".into(),
                ))
            }
            None => None,
        };

        let (node, consumed, used_keys) = ast_formatted_value_with_nested(
            selected,
            field.format_spec.as_deref(),
            conversion.as_deref(),
            &mut var_map,
            seq_ctr,
        )?;
        seq_ctr += consumed;
        if !aggressive {
            for k in used_keys {
                var_map.remove(&k);
            }
        }
        new_segments.push(node);
    }

    if !aggressive && (!var_map.is_empty() || has_double_star) {
        return Err(FlyntError::Generic(
            "Some variables were never used - skipping conversion, it's a risk of bug.".into(),
        ));
    }

    // All-literal result collapses to a plain string constant (no `f` prefix).
    if new_segments
        .iter()
        .all(|s| matches!(s, InterpolatedStringElement::Literal(_)))
    {
        let mut combined = String::new();
        for s in &new_segments {
            if let InterpolatedStringElement::Literal(lit) = s {
                combined.push_str(&lit.value);
            }
        }
        return Ok(new_string_literal(&combined));
    }

    Ok(new_joined_str(new_segments))
}

fn only_literal() -> FlyntError {
    FlyntError::ConversionRefused("Only literal format strings are supported".into())
}

// --- format-string brace validation ----------------------------------------

/// Reject the format strings on which CPython's `string.Formatter().parse`
/// raises `ValueError` (a lone `{`/`}`, an unclosed field, `{` inside a field
/// name, an unmatched `{` in a format spec, etc.). Mirrors CPython's
/// `MarkupIterator`/`parse_field` in `Objects/stringlib/unicode_format.h`. The
/// exact message is irrelevant (Python catches the `ValueError` and skips the
/// chunk); returning any `Err` reproduces that.
fn validate_format_string(s: &str) -> Result<(), FlyntError> {
    let cs: Vec<char> = s.chars().collect();
    let n = cs.len();
    let mut i = 0;
    while i < n {
        while i < n && cs[i] != '{' && cs[i] != '}' {
            i += 1;
        }
        if i >= n {
            break;
        }
        let at_end = i + 1 >= n;
        if cs[i] == '}' {
            if at_end || cs[i + 1] != '}' {
                return Err(fmt_value_error("Single '}' encountered in format string"));
            }
            i += 2; // literal '}}'
            continue;
        }
        // cs[i] == '{'
        if at_end {
            return Err(fmt_value_error("Single '{' encountered in format string"));
        }
        if cs[i + 1] == '{' {
            i += 2; // literal '{{'
            continue;
        }
        i = validate_field(&cs, i + 1)?;
    }
    Ok(())
}

/// Validate a single replacement field starting just after its opening `{`.
/// Returns the index just past the field's closing `}`.
fn validate_field(cs: &[char], mut i: usize) -> Result<usize, FlyntError> {
    let n = cs.len();
    // Field name: up to '}', ':' or '!'; '[' … ']' is skipped; nested '{' errors.
    let mut term = '\0';
    let mut found = false;
    while i < n {
        match cs[i] {
            '{' => return Err(fmt_value_error("unexpected '{' in field name")),
            '[' => {
                i += 1;
                while i < n && cs[i] != ']' {
                    i += 1;
                }
                continue; // ']' (or end) processed by the next iteration
            }
            c @ ('}' | ':' | '!') => {
                term = c;
                found = true;
                break;
            }
            _ => i += 1,
        }
    }
    if !found {
        return Err(fmt_value_error("expected '}' before end of string"));
    }
    if term == '}' {
        return Ok(i + 1);
    }
    if term == '!' {
        i += 1; // past '!'
        if i >= n {
            return Err(fmt_value_error(
                "end of string while looking for conversion specifier",
            ));
        }
        i += 1; // past the conversion character
        if i >= n {
            // e.g. `{x!}` — the conversion consumed `}`; CPython then enters the
            // format-spec loop which immediately hits end-of-string.
            return Err(fmt_value_error("unmatched '{' in format spec"));
        }
        match cs[i] {
            '}' => return Ok(i + 1),
            ':' => {} // fall through to format-spec parsing
            _ => {
                return Err(fmt_value_error(
                    "expected ':' after conversion specifier",
                ))
            }
        }
    }
    // Format spec (term == ':' or after a conversion): brace-count to the close.
    i += 1; // past ':'
    let mut count = 1;
    while i < n {
        match cs[i] {
            '{' => count += 1,
            '}' => {
                count -= 1;
                if count == 0 {
                    return Ok(i + 1);
                }
            }
            _ => {}
        }
        i += 1;
    }
    Err(fmt_value_error("unmatched '{' in format spec"))
}

/// A `ValueError`-equivalent from format-string parsing. Python raises a plain
/// `ValueError` here (not `ConversionRefused`); both are caught by
/// `transform_chunk` and increment `invalid_conversions`.
fn fmt_value_error(msg: &str) -> FlyntError {
    FlyntError::Generic(msg.to_string())
}

fn key_display(key: &FieldKey) -> String {
    match key {
        FieldKey::Index(i) => i.to_string(),
        FieldKey::Name(n) => n.clone(),
    }
}

// --- inserted-value constant scanning --------------------------------------

/// Collected string/bytes constant values found anywhere under an expression.
/// String values include f-string literal parts (Python treats those as
/// `Constant(str)` nodes reachable via `ast.walk`); bytes values are Latin-1
/// decoded, matching the Python refusal check.
pub(crate) struct ConstantScan {
    pub strings: Vec<String>,
    pub bytes_latin1: Vec<String>,
}

pub(crate) fn scan_constants(expr: &Expr) -> ConstantScan {
    let mut scanner = ConstScanner {
        strings: Vec::new(),
        bytes_latin1: Vec::new(),
    };
    scanner.visit_expr(expr);
    ConstantScan {
        strings: scanner.strings,
        bytes_latin1: scanner.bytes_latin1,
    }
}

struct ConstScanner {
    strings: Vec<String>,
    bytes_latin1: Vec<String>,
}

impl<'a> Visitor<'a> for ConstScanner {
    fn visit_expr(&mut self, expr: &'a Expr) {
        match expr {
            Expr::StringLiteral(s) => self.strings.push(s.value.to_str().to_string()),
            Expr::BytesLiteral(b) => {
                self.bytes_latin1
                    .push(b.value.bytes().map(|byte| byte as char).collect());
            }
            Expr::FString(fs) => {
                for part in fs.value.iter() {
                    match part {
                        FStringPart::Literal(lit) => self.strings.push(lit.value.to_string()),
                        FStringPart::FString(f) => {
                            for el in f.elements.iter() {
                                if let InterpolatedStringElement::Literal(l) = el {
                                    self.strings.push(l.value.to_string());
                                }
                            }
                        }
                    }
                }
            }
            _ => {}
        }
        walk_expr(self, expr);
    }
}

/// Refuse when an inserted constant contains a character that can't appear in an
/// f-string expression part. Port of the `joined_string` preflight loop.
fn check_no_backslash(expr: &Expr) -> Result<(), FlyntError> {
    let scan = scan_constants(expr);
    for v in scan.strings.iter().chain(scan.bytes_latin1.iter()) {
        if bad_in_fstring_part(v) {
            return Err(FlyntError::ConversionRefused(
                "f-string expression part cannot include a backslash".into(),
            ));
        }
    }
    Ok(())
}

fn bad_in_fstring_part(v: &str) -> bool {
    v.contains('\n')
        || v.contains('\t')
        || v.contains('\r')
        || v.contains('\\')
        || v == "\""
        || v == "'"
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::astutils::{ast_to_string, parse_expr};

    fn conv(code: &str, aggressive: bool) -> Result<String, FlyntError> {
        let node = parse_expr(code).unwrap();
        joined_string(&node, aggressive).and_then(|e| ast_to_string(&e))
    }

    #[test]
    fn basic_positional() {
        assert_eq!(conv(r#""{} {}".format(a, b)"#, false).unwrap(), "f'{a} {b}'");
    }

    #[test]
    fn reordered_positional() {
        assert_eq!(conv(r#""{1} {0}".format(a, b)"#, false).unwrap(), "f'{b} {a}'");
    }

    #[test]
    fn attribute_suffix() {
        assert_eq!(conv(r#""{x.y}".format(x=z)"#, false).unwrap(), "f'{z.y}'");
        assert_eq!(conv(r#""{0.y}".format(z)"#, false).unwrap(), "f'{z.y}'");
        assert_eq!(conv(r#""{.y}".format(z)"#, false).unwrap(), "f'{z.y}'");
    }

    #[test]
    fn all_constant_folds_to_plain_string() {
        // No `f` prefix — every segment is literal.
        let out = conv(r#""lit {}".format("x")"#, false).unwrap();
        assert_eq!(out, "'lit x'");
    }

    #[test]
    fn indexed_name_refused() {
        assert!(matches!(
            conv(r#""{a[b]}".format(a=a)"#, false),
            Err(FlyntError::Generic(_))
        ));
    }

    #[test]
    fn reused_variable_refused_non_aggressive() {
        assert!(matches!(
            conv(r#""{0} {0}".format(arg)"#, false),
            Err(FlyntError::ConversionRefused(_))
        ));
    }

    #[test]
    fn reused_variable_ok_aggressive() {
        assert_eq!(conv(r#""{0} {0}".format(arg)"#, true).unwrap(), "f'{arg} {arg}'");
    }

    #[test]
    fn unused_variable_refused_non_aggressive() {
        assert!(conv(r#""{}{}".format(a)"#, false).is_err());
        assert!(conv(r#""{a}{b}".format(a=a)"#, false).is_err());
    }

    #[test]
    fn backslash_in_inserted_string_refused() {
        assert!(matches!(
            conv(r#""{}".format("\n".join(items))"#, false),
            Err(FlyntError::ConversionRefused(_))
        ));
        assert!(matches!(
            conv(r#""{}".format(b"\n")"#, false),
            Err(FlyntError::ConversionRefused(_))
        ));
    }

    #[test]
    fn nested_format_spec() {
        assert_eq!(conv(r#""{:{}}".format(x, y)"#, false).unwrap(), "f'{x:{y}}'");
        assert_eq!(
            conv(r#""{:{fill}}".format(x, fill=c)"#, false).unwrap(),
            "f'{x:{c}}'"
        );
        assert_eq!(
            conv(r#""{} {:>{}}".format(a, b, c)"#, false).unwrap(),
            "f'{a} {b:>{c}}'"
        );
    }

    #[test]
    fn double_star_kwargs_refused() {
        assert!(conv(r#""{some_name}".format(**kwargs)"#, false).is_err());
    }

    #[test]
    fn lone_brace_refused() {
        // Required noop cases from test_transform.py.
        assert!(conv("'{'.format(a)", false).is_err());
        assert!(conv("'}'.format(a)", false).is_err());
    }

    #[test]
    fn validate_matches_formatter_errors() {
        // Valid strings pass.
        for ok in ["{}", "{{}}", "{x}", "{x!r}", "{x:>5}", "{x:{w}}", "{0[a]}", "{{lit}}"] {
            assert!(validate_format_string(ok).is_ok(), "{ok:?} should be valid");
        }
        // Malformed strings are rejected (mirrors Formatter.parse ValueError).
        for bad in ["{", "}", "a{b", "a}b", "{x", "{}}", "{{}", "{ {1} }", "{x!rq}"] {
            assert!(validate_format_string(bad).is_err(), "{bad:?} should be invalid");
        }
    }
}
