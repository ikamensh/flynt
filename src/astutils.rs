//! Port of src/flynt/utils/utils.py — AST helpers and the unparser wrapper.
//!
//! Owner: task #4 (core utils).
//!
//! Contract notes:
//! - `ast_to_string` must match CPython `ast.unparse` output (plus flynt's
//!   ternary-paren cleanup) on the expression subset flynt emits. See the
//!   "CPython-compatible unparsing" section below for how ruff's `Generator`
//!   is steered (and, for f-strings, replaced) to achieve byte equality.
//! - The AST-building helpers (`ast_string_node`, `ast_formatted_value`,
//!   `ast_formatted_value_with_nested`, `new_joined_str`) are consumed by the
//!   transform modules (tasks #5/#6/#8). Because ruff models an f-string as a
//!   list of `InterpolatedStringElement`s (literal | interpolation) rather than
//!   CPython's `JoinedStr.values = [Constant | FormattedValue]`, these helpers
//!   return `InterpolatedStringElement` where the Python originals return
//!   `Constant | FormattedValue`. Assemble a finished f-string expression with
//!   `new_joined_str`.

use std::collections::{HashMap, HashSet};

use ruff_python_ast::str::{Quote, TripleQuotes};
use ruff_python_ast::str_prefix::StringLiteralPrefix;
use ruff_python_ast::visitor::{walk_expr, Visitor};
use ruff_python_ast::{
    self as ast, AtomicNodeIndex, ConversionFlag, Expr, ExprStringLiteral, FString, FStringFlags,
    FStringPart, InterpolatedElement, InterpolatedStringElement, InterpolatedStringElements,
    InterpolatedStringFormatSpec, StringLiteral, StringLiteralFlags, StringLiteralValue,
};
use ruff_python_codegen::{Generator, Indentation};
use ruff_python_parser::{parse_expression, parse_unchecked, Mode as ParseMode, ParseOptions};
use ruff_python_ast::token::TokenKind;
use ruff_source_file::LineEnding;
use ruff_text_size::TextRange;

use crate::error::FlyntError;
use crate::quotes;

// ---------------------------------------------------------------------------
// CPython-compatible unparsing
//
// CPython `ast.unparse` renders:
// - plain string/bytes constants via `repr()` (single-line, `'` preference with
//   repr's switch-to-`"` rule);
// - f-strings via `visit_JoinedStr`: each part is rendered first, then a
//   delimiter is chosen with an avoid-escape preference over `'`, `"`, `"""`,
//   `'''` (constants narrow the candidates hard, expression parts softly), so
//   literal parts never carry escaped quotes (`_str_literal_helper`).
//
// ruff's `Generator` instead escapes the delimiter quote inside f-string
// literal parts unconditionally, which leaves spurious `\'` when flynt later
// transplants the delimiter with set_quote_type (django oracle regression).
//
// Strategy:
// - `prepare_for_unparse` normalises every string/bytes literal's flags to
//   repr defaults (single quote, no triple, no raw) and stamps every *nested*
//   f-string with the CPython-chosen delimiter, so ruff's renderer picks the
//   right quote wherever ruff does the rendering.
// - a top-level f-string is assembled by `unparse_fstring_cpython`, a faithful
//   port of `visit_JoinedStr` + `_str_literal_helper`, so its body is
//   byte-identical to CPython even for triple-quoted delimiters.
// ---------------------------------------------------------------------------

/// Unparse an expression exactly like CPython `ast.unparse`.
fn unparse(node: &Expr) -> Result<String, FlyntError> {
    let mut node = node.clone();
    prepare_for_unparse(&mut node);
    if let Expr::FString(f) = &node {
        return unparse_fstring_cpython(f);
    }
    let indent = Indentation::default();
    Ok(Generator::new(&indent, LineEnding::Lf).expr(&node))
}

/// repr-style flags for a plain string constant: single-quote preference (the
/// escape layer applies repr's switch rule), single-line, no raw prefix. The
/// legacy `u` prefix survives, as in CPython's `visit_Constant`.
fn repr_string_flags(old: StringLiteralFlags) -> StringLiteralFlags {
    let flags = StringLiteralFlags::empty();
    if matches!(old.prefix(), StringLiteralPrefix::Unicode) {
        flags.with_prefix(StringLiteralPrefix::Unicode)
    } else {
        flags
    }
}

/// Normalise literal flags throughout the tree (post-order) so ruff's
/// `Generator` reproduces CPython's rendering; see module comment above.
fn prepare_for_unparse(expr: &mut Expr) {
    crate::fstr_lint::for_each_child_expr_mut(expr, &mut prepare_for_unparse);
    match expr {
        Expr::StringLiteral(s) => {
            for part in s.value.iter_mut() {
                part.flags = repr_string_flags(part.flags);
            }
        }
        Expr::BytesLiteral(b) => {
            for part in b.value.iter_mut() {
                part.flags = ast::BytesLiteralFlags::empty();
            }
        }
        Expr::FString(fs) => {
            for part in fs.value.iter_mut() {
                match part {
                    FStringPart::Literal(lit) => {
                        lit.flags = repr_string_flags(lit.flags);
                    }
                    FStringPart::FString(f) => {
                        // Children are already prepared; pick the CPython
                        // delimiter so ruff renders nested f-strings with it.
                        let parts = collect_fstring_parts(&f.elements);
                        let delim = select_fstring_quote(&parts).unwrap_or("'");
                        let (q, t) = delim_flags(delim);
                        f.flags = FStringFlags::empty()
                            .with_quote_style(q)
                            .with_triple_quotes(t);
                    }
                }
            }
        }
        _ => {}
    }
}

/// Python `_ALL_QUOTES` order: `'`, `"`, `"""`, `'''`.
const ALL_FSTRING_QUOTES: [&str; 4] = ["'", "\"", "\"\"\"", "'''"];

fn delim_flags(delim: &str) -> (Quote, TripleQuotes) {
    match delim {
        "'" => (Quote::Single, TripleQuotes::No),
        "\"" => (Quote::Double, TripleQuotes::No),
        "\"\"\"" => (Quote::Double, TripleQuotes::Yes),
        _ => (Quote::Single, TripleQuotes::Yes),
    }
}

/// One rendered f-string part, mirroring CPython's buffered
/// `(value, is_constant)` pairs in `visit_JoinedStr`:
/// - `canonical` is the text with backslash/non-printable/`\n`/`\t` escapes but
///   quotes UNescaped (CPython's `escape_char` output; braces already doubled);
/// - `raw_single` additionally escapes `'` (what `repr` forced to single quotes
///   would produce — used by the repr fallback paths).
struct FsPart {
    canonical: String,
    raw_single: String,
    is_constant: bool,
}

/// Render one f-string element through ruff (a temporary single-element
/// f-string with default flags) and strip the `f'`…`'` wrapper.
fn render_element_via_ruff(element: &InterpolatedStringElement) -> String {
    let temp = FString {
        range: TextRange::default(),
        node_index: AtomicNodeIndex::default(),
        elements: InterpolatedStringElements::from(vec![element.clone()]),
        flags: FStringFlags::empty(),
    };
    let expr = Expr::from(temp);
    let indent = Indentation::default();
    let text = Generator::new(&indent, LineEnding::Lf).expr(&expr);
    debug_assert!(text.starts_with("f'") && text.ends_with('\''));
    text[2..text.len() - 1].to_string()
}

/// Undo the escaping of `'` that ruff's single-quote-preferred body writer may
/// have applied, yielding CPython's `escape_char` canonical text. `\\` pairs
/// are honoured left-to-right so escaped backslashes are never misread.
fn unescape_single_quotes(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    let mut chars = s.chars();
    while let Some(c) = chars.next() {
        if c == '\\' {
            match chars.next() {
                Some('\'') => out.push('\''),
                Some(other) => {
                    out.push('\\');
                    out.push(other);
                }
                None => out.push('\\'),
            }
        } else {
            out.push(c);
        }
    }
    out
}

fn literal_fs_part(value: &str) -> FsPart {
    let rendered = render_element_via_ruff(&ast_string_node(value));
    let canonical = unescape_single_quotes(&rendered);
    let raw_single = canonical.replace('\'', "\\'");
    FsPart {
        canonical,
        raw_single,
        is_constant: true,
    }
}

/// Flatten an element list into rendered parts (constants and interpolations).
fn collect_fstring_parts(elements: &InterpolatedStringElements) -> Vec<FsPart> {
    let mut parts = Vec::new();
    for element in elements {
        match element {
            InterpolatedStringElement::Literal(lit) => parts.push(literal_fs_part(&lit.value)),
            InterpolatedStringElement::Interpolation(_) => {
                let body = render_element_via_ruff(element);
                parts.push(FsPart {
                    canonical: body.clone(),
                    raw_single: body,
                    is_constant: false,
                });
            }
        }
    }
    parts
}

/// Result of `_str_literal_helper` for one constant part.
enum HelperResult {
    Ok {
        text: String,
        quotes: Vec<&'static str>,
    },
    /// The repr-fallback quote is disjoint from the candidates: CPython sets
    /// `fallback_to_repr` for the whole JoinedStr.
    GlobalFallback,
}

/// Faithful port of CPython `_str_literal_helper` with
/// `escape_special_whitespace=True`, operating on the already-escaped
/// `canonical` text (quote presence and `\n` checks are unaffected by content
/// escaping, which never adds or removes quote/newline characters).
fn str_literal_helper(part: &FsPart, quote_types: &[&'static str]) -> HelperResult {
    let canonical = &part.canonical;
    let mut possible: Vec<&'static str> = quote_types.to_vec();
    if canonical.contains('\n') {
        possible.retain(|q| q.len() == 3);
    }
    possible.retain(|q| !canonical.contains(q));
    if possible.is_empty() {
        // CPython: string = repr(original); quote = first candidate containing
        // repr's quote char (repr picks `"` only when the text has `'` and no
        // `"`); no such candidate -> disjoint -> global fallback.
        let has_sq = canonical.contains('\'');
        let has_dq = canonical.contains('"');
        let (content, repr_quote) = if has_sq && !has_dq {
            (canonical.clone(), '"')
        } else {
            (part.raw_single.clone(), '\'')
        };
        return match quote_types.iter().copied().find(|q| q.contains(repr_quote)) {
            Some(q) => HelperResult::Ok {
                text: content,
                quotes: vec![q],
            },
            None => HelperResult::GlobalFallback,
        };
    }
    let mut text = canonical.clone();
    if let Some(last) = text.chars().last() {
        // Stable sort, non-matching quotes first (Python bool sort key), then
        // escape a final char that matches the first candidate's quote char
        // (only reachable for triple quotes).
        possible.sort_by_key(|q| q.starts_with(last));
        if possible[0].starts_with(last) {
            let cut = text.len() - last.len_utf8();
            text = format!("{}\\{}", &text[..cut], last);
        }
    }
    HelperResult::Ok {
        text,
        quotes: possible,
    }
}

/// CPython `visit_JoinedStr` delimiter selection + body assembly over rendered
/// parts. Returns `(delimiter, body)`.
fn select_and_render_fstring(parts: &[FsPart]) -> Result<(&'static str, String), FlyntError> {
    let mut quote_types: Vec<&'static str> = ALL_FSTRING_QUOTES.to_vec();
    let mut helper_texts: Vec<Option<String>> = vec![None; parts.len()];
    let mut fallback = false;

    for (i, part) in parts.iter().enumerate() {
        if part.is_constant {
            match str_literal_helper(part, &quote_types) {
                HelperResult::Ok { text, quotes } => {
                    quote_types = quotes;
                    helper_texts[i] = Some(text);
                }
                HelperResult::GlobalFallback => {
                    fallback = true;
                    break;
                }
            }
        } else {
            if part.canonical.contains('\n') {
                let multi: Vec<&'static str> =
                    quote_types.iter().copied().filter(|q| q.len() == 3).collect();
                if multi.is_empty() {
                    // CPython: `assert quote_types` fires; flynt catches the
                    // AssertionError and refuses the conversion.
                    return Err(FlyntError::Generic(
                        "no multi-quote delimiter available for f-string with newline in expression"
                            .to_string(),
                    ));
                }
                quote_types = multi;
            }
            let new: Vec<&'static str> = quote_types
                .iter()
                .copied()
                .filter(|q| !part.canonical.contains(q))
                .collect();
            if !new.is_empty() {
                quote_types = new;
            }
        }
    }

    let mut body = String::new();
    if fallback {
        // Whole-string repr fallback: `'''` delimiter, every constant rendered
        // repr-style with `'` forced (CPython's `repr('"' + value)` trick).
        quote_types = vec!["'''"];
        for part in parts {
            body.push_str(if part.is_constant {
                &part.raw_single
            } else {
                &part.canonical
            });
        }
    } else {
        for (i, part) in parts.iter().enumerate() {
            match &helper_texts[i] {
                Some(text) => body.push_str(text),
                None => body.push_str(&part.canonical),
            }
        }
    }
    Ok((quote_types[0], body))
}

/// Delimiter only (for stamping nested f-string flags).
fn select_fstring_quote(parts: &[FsPart]) -> Result<&'static str, FlyntError> {
    select_and_render_fstring(parts).map(|(q, _)| q)
}

/// Assemble a top-level f-string exactly like CPython `visit_JoinedStr`.
/// Implicitly concatenated parts are merged into one f-string, mirroring
/// CPython's single merged `JoinedStr` node.
fn unparse_fstring_cpython(f: &ast::ExprFString) -> Result<String, FlyntError> {
    let mut parts: Vec<FsPart> = Vec::new();
    for part in f.value.as_slice() {
        match part {
            FStringPart::Literal(lit) => parts.push(literal_fs_part(&lit.value)),
            FStringPart::FString(fs) => parts.extend(collect_fstring_parts(&fs.elements)),
        }
    }
    let (delim, body) = select_and_render_fstring(&parts)?;
    Ok(format!("f{delim}{body}{delim}"))
}

/// Port of ast_to_string (ast.unparse + ternary-paren cleanup).
///
/// `ast.unparse` wraps ternary (`IfExp`) expressions inside replacement fields
/// in redundant parentheses, e.g. `f"{(a if c else b)}"`; flynt strips those to
/// match its historical astor-based output. We reproduce exactly that: unparse,
/// right-strip, then (for f-strings only) drop `{( … if … else … )}` parens.
///
/// Known, deliberate divergences from CPython `ast.unparse` (all in the
/// "redundant parentheses CPython adds, ruff omits" family; semantically
/// identical output, kept as documented improvements):
/// - generator expressions as sole call argument: `join(g for g in x)` vs
///   CPython's `join((g for g in x))`;
/// - later operands of a BoolOp at lower precedence: `a and not b` vs
///   CPython's `a and (not b)` (CPython requires increasing precedence across
///   boolop operands);
/// - a ternary/lambda/tuple as a replacement-field value WITH a format spec:
///   `f'{a if b else c:>5}'` vs CPython's `f'{(a if b else c):>5}'`.
pub fn ast_to_string(node: &Expr) -> Result<String, FlyntError> {
    let mut txt = unparse(node)?.trim_end().to_string();
    // CPython `ast.unparse` always parenthesises a (non-empty) tuple; ruff omits
    // the parens at statement/expression top level. Restore them so top-level
    // tuples match `ast.unparse` (relevant to AstChunk, which then strips them).
    if let Expr::Tuple(t) = node {
        if !t.is_empty() && !txt.starts_with('(') {
            txt = format!("({txt})");
        }
    }
    if matches!(node, Expr::FString(_)) {
        txt = strip_ternary_parens(&txt);
    }
    Ok(txt)
}

/// Port of fixup_transformed: inline nested f-strings, unparse, normalise the
/// outer quote to `quote_type` (default logic mirrors the Python), and escape
/// literal newlines/tabs. This is the function the transform pipelines call to
/// turn a freshly built f-string/constant node into final source text; the
/// `set_quote_type` step here is what fixes the outer delimiter (ruff's
/// `Generator` prefers single quotes where CPython would pick double — that
/// difference is entirely absorbed here).
pub fn fixup_transformed(
    mut tree: Expr,
    quote_type: Option<quotes::QuoteType>,
) -> Result<String, FlyntError> {
    crate::fstr_lint::inline_fstrings(&mut tree);
    let mut new_code = ast_to_string(&tree)?;
    let quote_type = quote_type.or_else(|| match &tree {
        Expr::StringLiteral(_) | Expr::FString(_) => Some(quotes::QuoteType::Double),
        _ if new_code.starts_with("f\"\"\"")
            || new_code.starts_with("'''")
            || new_code.starts_with("\"\"\"") =>
        {
            Some(quotes::QuoteType::Double)
        }
        _ => None,
    });
    if let Some(qt) = quote_type {
        new_code = quotes::set_quote_type(&new_code, qt);
    }
    new_code = new_code.replace('\n', "\\n").replace('\t', "\\t");
    Ok(new_code)
}

/// Faithful reimplementation of flynt's
/// `re.sub(r"\{\(([^{}]+?\sif\s[^{}]+?\selse\s[^{}]+?)\)\}", r"{\1}", txt)`.
///
/// Finds `{(` … `)}` where the parenthesised body contains no braces and has the
/// shape `X if Y else Z`, and removes the inner parentheses. The `\s` classes
/// and lazy `[^{}]+?` runs are matched with the same left-to-right,
/// leftmost-shortest, non-overlapping semantics as Python's `re`.
fn strip_ternary_parens(s: &str) -> String {
    let cs: Vec<char> = s.chars().collect();
    let n = cs.len();
    let mut out = String::with_capacity(s.len());
    let mut i = 0;
    while i < n {
        if cs[i] == '{' && i + 1 < n && cs[i + 1] == '(' {
            if let Some((group_start, group_end, match_end)) = match_ternary(&cs, i) {
                out.push('{');
                out.extend(&cs[group_start..group_end]);
                out.push('}');
                i = match_end;
                continue;
            }
        }
        out.push(cs[i]);
        i += 1;
    }
    out
}

/// Match `\s KEYWORD \s` starting at `pos`; returns the index just past the
/// trailing whitespace, or `None`.
fn match_ws_kw_ws(cs: &[char], pos: usize, kw: &str) -> Option<usize> {
    let n = cs.len();
    if pos >= n || !cs[pos].is_whitespace() {
        return None;
    }
    let mut p = pos + 1;
    for kc in kw.chars() {
        if p >= n || cs[p] != kc {
            return None;
        }
        p += 1;
    }
    if p >= n || !cs[p].is_whitespace() {
        return None;
    }
    Some(p + 1)
}

/// Attempt to match the ternary-paren pattern anchored at `cs[i] == '{'`,
/// `cs[i+1] == '('`. Returns `(group_start, group_end, match_end)` where the
/// group is `cs[group_start..group_end]` (the body without the parens) and
/// `match_end` is the index just past the closing `)}`.
fn match_ternary(cs: &[char], i: usize) -> Option<(usize, usize, usize)> {
    let n = cs.len();
    let a_start = i + 2;
    let non_brace = |c: char| c != '{' && c != '}';

    // A: lazy `[^{}]+?` (>= 1)
    let mut a_end = a_start;
    loop {
        if a_end - a_start >= 1 {
            if let Some(b_start) = match_ws_kw_ws(cs, a_end, "if") {
                // B: lazy `[^{}]+?` (>= 1)
                let mut b_end = b_start;
                loop {
                    if b_end - b_start >= 1 {
                        if let Some(c_start) = match_ws_kw_ws(cs, b_end, "else") {
                            // C: lazy `[^{}]+?` (>= 1), then literal `)}`
                            let mut c_end = c_start;
                            loop {
                                if c_end - c_start >= 1
                                    && c_end + 1 < n
                                    && cs[c_end] == ')'
                                    && cs[c_end + 1] == '}'
                                {
                                    return Some((a_start, c_end, c_end + 2));
                                }
                                if c_end < n && non_brace(cs[c_end]) {
                                    c_end += 1;
                                } else {
                                    break;
                                }
                            }
                        }
                    }
                    if b_end < n && non_brace(cs[b_end]) {
                        b_end += 1;
                    } else {
                        break;
                    }
                }
            }
        }
        if a_end < n && non_brace(cs[a_end]) {
            a_end += 1;
        } else {
            break;
        }
    }
    None
}

/// Port of str_in_str: true if a formatted value contains a string constant or
/// a nested JoinedStr somewhere inside its value subtree (format specs and the
/// immediate value node itself are not counted — see the Python
/// `StringInStringVisitor`).
pub fn str_in_str(node: &Expr) -> bool {
    let mut v = StringInStringVisitor {
        found: false,
        in_fmt_value: false,
    };
    v.visit_expr(node);
    v.found
}

struct StringInStringVisitor {
    found: bool,
    in_fmt_value: bool,
}

impl<'a> Visitor<'a> for StringInStringVisitor {
    fn visit_expr(&mut self, expr: &'a Expr) {
        match expr {
            // visit_JoinedStr
            Expr::FString(_) => {
                if self.in_fmt_value {
                    self.found = true;
                }
                walk_expr(self, expr);
            }
            // visit_Constant(str)
            Expr::StringLiteral(_) => {
                if self.in_fmt_value {
                    self.found = true;
                }
            }
            // generic_visit
            _ => walk_expr(self, expr),
        }
    }

    fn visit_interpolated_string_element(&mut self, element: &'a InterpolatedStringElement) {
        match element {
            // visit_FormattedValue
            InterpolatedStringElement::Interpolation(interp) => {
                if self.in_fmt_value {
                    // Already inside a formatted value: recurse into the value's
                    // children (generic_visit(node.value)), stay in_fmt_value,
                    // do NOT visit the format spec.
                    walk_expr(self, &interp.expression);
                } else {
                    self.in_fmt_value = true;
                    walk_expr(self, &interp.expression);
                    self.in_fmt_value = false;
                }
            }
            // A literal element ↔ Constant(str) inside JoinedStr.values.
            InterpolatedStringElement::Literal(_) => {
                if self.in_fmt_value {
                    self.found = true;
                }
            }
        }
    }
}

/// Port of contains_comment: does this snippet contain a `#` comment outside of
/// string literals? Python tokenizes; we scan ruff's tokens for `Comment`.
pub fn contains_comment(code: &str) -> bool {
    let parsed = parse_unchecked(code, ParseOptions::from(ParseMode::Module));
    parsed
        .tokens()
        .iter()
        .any(|t| t.kind() == TokenKind::Comment)
}

// --- unicode escape preservation ------------------------------------------

/// Decode a single escape sequence matched by `unicode_escape_re` into its
/// character, mirroring `codecs.decode(esc, "unicode_escape")`. Returns `None`
/// when the sequence can't be decoded (Python's `except: continue`). Named
/// escapes `\N{…}` are not supported (they never appear in flynt's corpus and
/// would require a Unicode-name database); such sequences are skipped.
fn decode_escape(esc: &[char]) -> Option<char> {
    // esc[0] == '\\'
    let radixed = |digits: &[char], radix: u32| -> Option<char> {
        let s: String = digits.iter().collect();
        u32::from_str_radix(&s, radix).ok().and_then(char::from_u32)
    };
    match esc.get(1)? {
        'u' => radixed(&esc[2..], 16),
        'U' => radixed(&esc[2..], 16),
        'x' => radixed(&esc[2..], 16),
        'N' => None,
        _ => radixed(&esc[1..], 8), // octal `\ooo`
    }
}

/// Scan `body` for the next escape sequence at or after `pos`. Returns the range
/// of chars `[start, end)` of the escape, mirroring `unicode_escape_re`.
fn next_escape(body: &[char], from: usize) -> Option<(usize, usize)> {
    let n = body.len();
    let is_hex = |c: char| c.is_ascii_hexdigit();
    let is_oct = |c: char| ('0'..='7').contains(&c);
    let mut i = from;
    while i < n {
        if body[i] == '\\' && i + 1 < n {
            let k = body[i + 1];
            let end = match k {
                'u' if i + 6 <= n && body[i + 2..i + 6].iter().all(|&c| is_hex(c)) => Some(i + 6),
                'U' if i + 10 <= n && body[i + 2..i + 10].iter().all(|&c| is_hex(c)) => {
                    Some(i + 10)
                }
                'x' if i + 4 <= n && body[i + 2..i + 4].iter().all(|&c| is_hex(c)) => Some(i + 4),
                'N' if i + 2 < n && body[i + 2] == '{' => {
                    // \N{...} — find closing '}' with at least one char inside.
                    let mut j = i + 3;
                    while j < n && body[j] != '}' {
                        j += 1;
                    }
                    if j < n && j > i + 3 {
                        Some(j + 1)
                    } else {
                        None
                    }
                }
                c if is_oct(c) => {
                    // \ooo — greedy 1..=3 octal digits.
                    let mut j = i + 2;
                    while j < n && j < i + 4 && is_oct(body[j]) {
                        j += 1;
                    }
                    Some(j)
                }
                _ => None,
            };
            if let Some(end) = end {
                return Some((i, end));
            }
        }
        i += 1;
    }
    None
}

/// Port of unicode_escape_map: map each decoded character to the list of escape
/// sequences (in order of appearance) used for it in the literal.
pub fn unicode_escape_map(literal: &str) -> Result<HashMap<String, Vec<String>>, FlyntError> {
    let body = quotes::remove_quotes(literal)?;
    let chars: Vec<char> = body.chars().collect();
    let mut mapping: HashMap<String, Vec<String>> = HashMap::new();
    let mut pos = 0;
    while let Some((start, end)) = next_escape(&chars, pos) {
        let esc = &chars[start..end];
        if let Some(ch) = decode_escape(esc) {
            let esc_str: String = esc.iter().collect();
            mapping.entry(ch.to_string()).or_default().push(esc_str);
        }
        pos = end;
    }
    Ok(mapping)
}

/// Port of apply_unicode_escape_map. Consumes `mapping` (Python mutates the dict
/// in place, popping escapes off the front as they are re-applied).
pub fn apply_unicode_escape_map(code: &str, mut mapping: HashMap<String, Vec<String>>) -> String {
    if mapping.is_empty() {
        return code.to_string();
    }
    let mut out = String::with_capacity(code.len());
    for ch in code.chars() {
        let key = ch.to_string();
        if let Some(escapes) = mapping.get_mut(&key) {
            if !escapes.is_empty() {
                out.push_str(&escapes.remove(0));
                continue;
            }
        }
        out.push(ch);
    }
    out
}

// --- AST construction helpers (consumed by the transform modules) ----------

fn dummy_range() -> TextRange {
    TextRange::default()
}

/// True if `node` is a plain string constant (Python `is_str_constant`).
pub fn is_str_constant(node: &Expr) -> bool {
    matches!(node, Expr::StringLiteral(_))
}

/// Port of ast_string_node: a literal f-string element carrying `value`
/// (CPython returns `ast.Constant(value=string)`; in ruff this is the literal
/// element that goes into an f-string's element list).
pub fn ast_string_node(value: &str) -> InterpolatedStringElement {
    InterpolatedStringElement::Literal(ast::InterpolatedStringLiteralElement {
        range: dummy_range(),
        node_index: AtomicNodeIndex::default(),
        value: value.into(),
    })
}

/// Build a plain string-literal expression (CPython `ast.Constant(value=str)`).
pub fn new_string_literal(value: &str) -> Expr {
    Expr::StringLiteral(ExprStringLiteral {
        range: dummy_range(),
        node_index: AtomicNodeIndex::default(),
        value: StringLiteralValue::single(StringLiteral {
            range: dummy_range(),
            node_index: AtomicNodeIndex::default(),
            value: value.into(),
            flags: StringLiteralFlags::empty(),
        }),
    })
}

/// Assemble a finished f-string expression (CPython `ast.JoinedStr(elements)`).
pub fn new_joined_str(elements: Vec<InterpolatedStringElement>) -> Expr {
    Expr::from(FString {
        range: dummy_range(),
        node_index: AtomicNodeIndex::default(),
        elements: InterpolatedStringElements::from(elements),
        flags: FStringFlags::empty(),
    })
}

fn conversion_from_str(conversion: Option<&str>) -> ConversionFlag {
    // Python: -1 if None else ord(conversion.replace("!", "")).
    match conversion.map(|c| c.replace('!', "")) {
        None => ConversionFlag::None,
        Some(c) => match c.as_str() {
            "s" => ConversionFlag::Str,
            "r" => ConversionFlag::Repr,
            "a" => ConversionFlag::Ascii,
            _ => ConversionFlag::None,
        },
    }
}

/// Port of ast_formatted_value: wrap `val` as an f-string interpolation element
/// (or a literal element when it is a bare string constant with no spec).
pub fn ast_formatted_value(
    val: Expr,
    fmt_str: Option<&str>,
    conversion: Option<&str>,
) -> Result<InterpolatedStringElement, FlyntError> {
    let mut var_map: HashMap<FieldKey, Expr> = HashMap::new();
    let (element, _consumed, _used) =
        formatted_value_impl(val, fmt_str, conversion, false, 0, &mut var_map)?;
    Ok(element)
}

/// Key type for the format-spec `var_map` (CPython uses `Union[str, int]`).
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum FieldKey {
    Index(usize),
    Name(String),
}

/// Port of ast_formatted_value_with_nested: like `ast_formatted_value` but
/// resolves nested field references (`{…}`) inside the format spec against
/// `var_map`. Returns `(element, implicit_count, used_keys)`.
pub fn ast_formatted_value_with_nested(
    val: Expr,
    fmt_str: Option<&str>,
    conversion: Option<&str>,
    var_map: &mut HashMap<FieldKey, Expr>,
    seq_ctr: usize,
) -> Result<(InterpolatedStringElement, usize, HashSet<FieldKey>), FlyntError> {
    formatted_value_impl(val, fmt_str, conversion, true, seq_ctr, var_map)
}

/// Shared implementation for the two public `ast_formatted_value*` helpers.
/// `resolve_nested` mirrors the Python `var_map is not None` gate: when set,
/// `{…}` fields in `fmt_str` are resolved against `var_map`.
fn formatted_value_impl(
    mut val: Expr,
    fmt_str: Option<&str>,
    conversion: Option<&str>,
    resolve_nested: bool,
    seq_ctr: usize,
    var_map: &mut HashMap<FieldKey, Expr>,
) -> Result<(InterpolatedStringElement, usize, HashSet<FieldKey>), FlyntError> {
    // Python: `if ast_to_string(val).startswith("{")` -> refuse.
    if ast_to_string(&val)?.starts_with('{') {
        return Err(FlyntError::ConversionRefused(
            "values starting with '{' are better left not transformed.".to_string(),
        ));
    }

    // Auto-convert str(x)/repr(x) with no spec into a conversion flag.
    let mut conversion = conversion.map(str::to_string);
    if fmt_str.map_or(true, str::is_empty) && conversion.is_none() {
        if let Expr::Call(call) = &val {
            if let Expr::Name(name) = call.func.as_ref() {
                let id = name.id.as_str();
                if (id == "str" || id == "repr")
                    && call.arguments.keywords.is_empty()
                    && call.arguments.args.len() == 1
                {
                    conversion = Some(if id == "str" { "!s" } else { "!r" }.to_string());
                    val = call.arguments.args[0].clone();
                }
            }
        }
    }

    let mut consumed = 0usize;
    let mut used_keys: HashSet<FieldKey> = HashSet::new();

    let format_spec: Option<InterpolatedStringFormatSpec> = match fmt_str {
        Some(fs) if !fs.is_empty() => {
            if resolve_nested && fs.contains('{') {
                let (spec, c, keys) = build_format_spec(fs, var_map, seq_ctr)?;
                consumed = c;
                used_keys = keys;
                Some(spec)
            } else {
                Some(format_spec_from_literal(fs))
            }
        }
        _ => None,
    };

    let conversion_flag = conversion_from_str(conversion.as_deref());

    // Python: `if format_spec is None and is_str_constant(val): return val`.
    if format_spec.is_none() && is_str_constant(&val) {
        if let Expr::StringLiteral(s) = &val {
            return Ok((ast_string_node(s.value.to_str()), consumed, used_keys));
        }
    }

    let element = InterpolatedStringElement::Interpolation(InterpolatedElement {
        range: dummy_range(),
        node_index: AtomicNodeIndex::default(),
        expression: Box::new(val),
        debug_text: None,
        conversion: conversion_flag,
        format_spec: format_spec.map(Box::new),
    });
    Ok((element, consumed, used_keys))
}

/// A format spec that is a single literal string (no nested fields).
fn format_spec_from_literal(fmt_str: &str) -> InterpolatedStringFormatSpec {
    InterpolatedStringFormatSpec {
        range: dummy_range(),
        node_index: AtomicNodeIndex::default(),
        elements: InterpolatedStringElements::from(vec![ast_string_node(fmt_str)]),
    }
}

/// Port of _build_format_spec: resolve `{…}` field references inside a format
/// spec against `var_map`, returning `(spec, implicit_count, used_keys)`.
fn build_format_spec(
    fmt_str: &str,
    var_map: &mut HashMap<FieldKey, Expr>,
    seq_ctr: usize,
) -> Result<(InterpolatedStringFormatSpec, usize, HashSet<FieldKey>), FlyntError> {
    let mut parts: Vec<InterpolatedStringElement> = Vec::new();
    let mut consumed = 0usize;
    let mut used_keys: HashSet<FieldKey> = HashSet::new();
    for field in stdlib_parse(fmt_str) {
        if !field.literal.is_empty() {
            parts.push(ast_string_node(&field.literal));
        }
        if let Some(field_name) = field.field_name {
            let key = if field_name.chars().all(|c| c.is_ascii_digit()) && !field_name.is_empty() {
                FieldKey::Index(field_name.parse().unwrap())
            } else if field_name.is_empty() {
                let k = FieldKey::Index(seq_ctr + consumed);
                consumed += 1;
                k
            } else {
                FieldKey::Name(field_name)
            };
            used_keys.insert(key.clone());
            let value = var_map.get(&key).cloned().ok_or_else(|| {
                FlyntError::Generic(format!("format spec references unknown field {key:?}"))
            })?;
            parts.push(InterpolatedStringElement::Interpolation(InterpolatedElement {
                range: dummy_range(),
                node_index: AtomicNodeIndex::default(),
                expression: Box::new(value),
                debug_text: None,
                conversion: ConversionFlag::None,
                format_spec: None,
            }));
        }
    }
    Ok((
        InterpolatedStringFormatSpec {
            range: dummy_range(),
            node_index: AtomicNodeIndex::default(),
            elements: InterpolatedStringElements::from(parts),
        },
        consumed,
        used_keys,
    ))
}

/// One parsed field from `string.Formatter().parse`, i.e. the 4-tuple
/// `(literal_text, field_name, format_spec, conversion)`. When there is no
/// replacement field, only `literal` is set (the others are `None`); when a
/// field *is* present, `format_spec` is `Some("")` even if empty (matching the
/// stdlib), and `conversion` is `Some(c)` for `!c`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FormatField {
    pub literal: String,
    pub field_name: Option<String>,
    pub format_spec: Option<String>,
    pub conversion: Option<char>,
}

/// Port of `stdlib_parse = string.Formatter().parse`.
///
/// Splits a format string into `FormatField` tuples, honoring `{{`/`}}` escapes,
/// bracketed field names (`d[a:b]`), `!conversion`, and nested `{…}` inside the
/// format spec. Used by the `.format()`-call transform (task #6) and by the
/// nested format-spec builder here.
pub fn stdlib_parse(s: &str) -> Vec<FormatField> {
    let cs: Vec<char> = s.chars().collect();
    let n = cs.len();
    let mut fields = Vec::new();
    let mut literal = String::new();
    let mut i = 0;

    let plain = |literal: String| FormatField {
        literal,
        field_name: None,
        format_spec: None,
        conversion: None,
    };

    while i < n {
        match cs[i] {
            '{' if i + 1 < n && cs[i + 1] == '{' => {
                literal.push('{');
                fields.push(plain(std::mem::take(&mut literal)));
                i += 2;
            }
            '}' if i + 1 < n && cs[i + 1] == '}' => {
                literal.push('}');
                fields.push(plain(std::mem::take(&mut literal)));
                i += 2;
            }
            '{' => {
                i += 1;
                // field_name: up to '!' / ':' / '}' at bracket depth 0.
                let mut name = String::new();
                let mut bracket_depth = 0i32;
                while i < n {
                    let c = cs[i];
                    if bracket_depth == 0 && (c == '!' || c == ':' || c == '}') {
                        break;
                    }
                    if c == '[' {
                        bracket_depth += 1;
                    } else if c == ']' {
                        bracket_depth -= 1;
                    }
                    name.push(c);
                    i += 1;
                }
                // conversion: '!' followed by one char.
                let mut conversion = None;
                if i < n && cs[i] == '!' {
                    if i + 1 < n {
                        conversion = Some(cs[i + 1]);
                    }
                    i += 2;
                }
                // format spec: ':' up to the field-closing '}' (nested '{…}' allowed).
                let mut format_spec = String::new();
                if i < n && cs[i] == ':' {
                    i += 1;
                    let mut brace_depth = 0i32;
                    while i < n {
                        let c = cs[i];
                        if c == '}' && brace_depth == 0 {
                            break;
                        }
                        if c == '{' {
                            brace_depth += 1;
                        } else if c == '}' {
                            brace_depth -= 1;
                        }
                        format_spec.push(c);
                        i += 1;
                    }
                }
                if i < n && cs[i] == '}' {
                    i += 1; // consume field-closing '}'
                }
                fields.push(FormatField {
                    literal: std::mem::take(&mut literal),
                    field_name: Some(name),
                    format_spec: Some(format_spec),
                    conversion,
                });
            }
            c => {
                literal.push(c);
                i += 1;
            }
        }
    }
    if !literal.is_empty() {
        fields.push(plain(literal));
    }
    fields
}

/// Port of get_str_value: the string value of a string constant (else error).
pub fn get_str_value(node: &Expr) -> Result<String, FlyntError> {
    match node {
        Expr::StringLiteral(s) => Ok(s.value.to_str().to_string()),
        _ => Err(FlyntError::Generic("Expected string constant".to_string())),
    }
}

/// Port of is_str_literal: a string constant or an f-string.
pub fn is_str_literal(node: &Expr) -> bool {
    matches!(node, Expr::StringLiteral(_) | Expr::FString(_))
}

/// Parse a standalone expression from source (helper for tests and callers).
pub fn parse_expr(src: &str) -> Result<Expr, FlyntError> {
    parse_expression(src)
        .map(|parsed| parsed.into_syntax().body.as_ref().clone())
        .map_err(|e| FlyntError::Generic(format!("parse error: {e}")))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn u(src: &str) -> String {
        ast_to_string(&parse_expr(src).unwrap()).unwrap()
    }

    #[test]
    fn ternary_paren_strip_basic() {
        // Both parenthesised and not collapse to the no-paren form.
        assert_eq!(strip_ternary_parens("f'{(a if b else c)}'"), "f'{a if b else c}'");
        assert_eq!(strip_ternary_parens("f'{a if b else c}'"), "f'{a if b else c}'");
    }

    #[test]
    fn ternary_paren_kept_with_format_spec() {
        // `)` not followed immediately by `}` -> parens kept.
        let s = "f'{(a if b else c):>{w}}'";
        assert_eq!(strip_ternary_parens(s), s);
    }

    #[test]
    fn ternary_multiple() {
        assert_eq!(
            strip_ternary_parens("f'{(a if b else c)}{(d if e else f)}'"),
            "f'{a if b else c}{d if e else f}'"
        );
    }

    #[test]
    fn str_in_str_cases() {
        assert!(str_in_str(&parse_expr("f\"{' '.join(lst)}\"").unwrap()));
        assert!(!str_in_str(&parse_expr("f'{x}'").unwrap()));
        assert!(!str_in_str(&parse_expr("f'{\"hello\"}'").unwrap()));
        assert!(str_in_str(&parse_expr("f'{a + \"b\"}'").unwrap()));
        assert!(!str_in_str(&parse_expr("f'{x:{\"fmt\"}}'").unwrap()));
    }

    #[test]
    fn contains_comment_cases() {
        assert!(contains_comment("x = 1  # c"));
        assert!(!contains_comment("x = 1"));
        assert!(!contains_comment("'a # not comment'"));
    }

    #[test]
    fn unicode_escape_roundtrip() {
        let map = unicode_escape_map("\"Feels {}\\u00B0F\"").unwrap();
        assert_eq!(map.get("°").unwrap(), &vec!["\\u00B0".to_string()]);
        let applied = apply_unicode_escape_map("Feels {}°F", map);
        assert_eq!(applied, "Feels {}\\u00B0F");
    }

    #[test]
    fn ast_to_string_roundtrips_expr() {
        assert_eq!(u("a % b"), "a % b");
        assert_eq!(u("f'{x!r}'"), "f'{x!r}'");
    }

    #[test]
    fn fstring_delimiter_avoids_escaping_quotes() {
        // The django oracle regression: single quotes in literal parts force a
        // `"` delimiter with NO `\'` escapes in the body (CPython
        // visit_JoinedStr avoid-escape preference).
        assert_eq!(
            u("f\"WHERE SEQUENCE_NAME = '{args['sq_name']}';\""),
            "f\"WHERE SEQUENCE_NAME = '{args['sq_name']}';\""
        );
        // Both quote chars in the literal parts -> triple delimiter, bare
        // quotes in the body. The stable sort prefers a delimiter whose quote
        // char differs from the part's trailing char, hence ''' here.
        assert_eq!(
            u("f\"\"\"EXECUTE IMMEDIATE 'CREATE SEQUENCE \"{args['sq_name']}\"';\"\"\""),
            "f'''EXECUTE IMMEDIATE 'CREATE SEQUENCE \"{args['sq_name']}\"';'''"
        );
    }

    #[test]
    fn fstring_delimiter_trailing_quote_escape() {
        // All surviving candidates start with the part's trailing char ->
        // triple delimiter with the final quote escaped (CPython rule).
        assert_eq!(
            u("f'x\\'\\'\\'y{v}z\"'"),
            "f\"\"\"x'''y{v}z\\\"\"\"\""
        );
    }

    #[test]
    fn fstring_delimiter_repr_fallback() {
        // A constant containing both triple-quote runs exhausts the candidates:
        // CPython falls back to repr for that part (single-quote escaping).
        assert_eq!(
            u("f'a\\'\\'\\'b\"\"\"c{v}'"),
            "f'a\\'\\'\\'b\"\"\"c{v}'"
        );
    }

    #[test]
    fn fixup_transplants_cleanly_to_triple() {
        // End-to-end shape of the oracle defect: a synthesized f-string with
        // single quotes around a field, transplanted to a triple-double
        // delimiter by fixup_transformed -> no stray backslashes.
        let els = vec![
            ast_string_node("WHERE SEQUENCE_NAME = '"),
            ast_formatted_value(name("args['sq_name']"), None, None).unwrap(),
            ast_string_node("';"),
        ];
        let out =
            fixup_transformed(new_joined_str(els), Some(quotes::QuoteType::TripleDouble)).unwrap();
        assert_eq!(out, "f\"\"\"WHERE SEQUENCE_NAME = '{args['sq_name']}';\"\"\"");
        assert!(!out.contains("\\'"));
    }

    #[test]
    fn top_level_tuple_gets_parens() {
        // ast.unparse wraps top-level tuples; ruff does not.
        assert_eq!(u("(1, 2)"), "(1, 2)");
        assert_eq!(u("1, 2"), "(1, 2)");
    }

    #[test]
    fn inner_string_quotes_forced_single() {
        // Inner string constants render single-quoted like CPython, regardless
        // of their original quote in source; the outer delimiter then avoids
        // the inner quotes (CPython visit_JoinedStr picks `"`).
        assert_eq!(u("f\"{d[\"a\"]}\""), "f\"{d['a']}\"");
        assert_eq!(u("f\"{\" \".join(x)}\""), "f\"{' '.join(x)}\"");
    }

    // --- helper construction tests (reference values from flynt itself) ---

    fn name(id: &str) -> Expr {
        parse_expr(id).unwrap()
    }

    fn build(elements: Vec<InterpolatedStringElement>) -> String {
        ast_to_string(&new_joined_str(elements)).unwrap()
    }

    #[test]
    fn helper_literal_and_value() {
        let els = vec![
            ast_string_node("x = "),
            ast_formatted_value(name("a"), None, None).unwrap(),
        ];
        assert_eq!(build(els), "f'x = {a}'");
    }

    #[test]
    fn helper_format_spec_and_conversion() {
        assert_eq!(
            build(vec![ast_formatted_value(name("a"), Some(">10"), None).unwrap()]),
            "f'{a:>10}'"
        );
        assert_eq!(
            build(vec![ast_formatted_value(name("a"), None, Some("!r")).unwrap()]),
            "f'{a!r}'"
        );
    }

    #[test]
    fn helper_str_repr_auto_conversion() {
        assert_eq!(
            build(vec![ast_formatted_value(name("str(x)"), None, None).unwrap()]),
            "f'{x!s}'"
        );
        assert_eq!(
            build(vec![ast_formatted_value(name("repr(x)"), None, None).unwrap()]),
            "f'{x!r}'"
        );
    }

    #[test]
    fn helper_bare_str_constant_becomes_literal() {
        // A bare string constant with no spec is returned as a literal element.
        let el = ast_formatted_value(name("'lit'"), None, None).unwrap();
        assert!(matches!(el, InterpolatedStringElement::Literal(_)));
        assert_eq!(build(vec![el]), "f'lit'");
    }

    #[test]
    fn helper_nested_format_spec() {
        // {0} explicit index.
        let mut var_map = HashMap::new();
        var_map.insert(FieldKey::Index(0), name("width"));
        let (node, consumed, used) =
            ast_formatted_value_with_nested(name("a"), Some("{0}"), None, &mut var_map, 0).unwrap();
        assert_eq!(build(vec![node]), "f'{a:{width}}'");
        assert_eq!(consumed, 0);
        assert_eq!(used, HashSet::from([FieldKey::Index(0)]));
    }

    #[test]
    fn helper_nested_format_spec_implicit() {
        // {}.{}f implicit indices consume seq positions.
        let mut var_map = HashMap::new();
        var_map.insert(FieldKey::Index(0), name("w"));
        var_map.insert(FieldKey::Index(1), name("p"));
        let (node, consumed, used) =
            ast_formatted_value_with_nested(name("a"), Some("{}.{}f"), None, &mut var_map, 0)
                .unwrap();
        assert_eq!(build(vec![node]), "f'{a:{w}.{p}f}'");
        assert_eq!(consumed, 2);
        assert_eq!(used, HashSet::from([FieldKey::Index(0), FieldKey::Index(1)]));
    }

    #[test]
    fn helper_new_string_literal_and_accessors() {
        let lit = new_string_literal("hi");
        assert_eq!(ast_to_string(&lit).unwrap(), "'hi'");
        assert!(is_str_constant(&lit));
        assert!(is_str_literal(&lit));
        assert_eq!(get_str_value(&lit).unwrap(), "hi");
        // f-strings are str literals but not str constants.
        let fs = name("f'{x}'");
        assert!(is_str_literal(&fs));
        assert!(!is_str_constant(&fs));
        assert!(get_str_value(&fs).is_err());
    }

    #[test]
    fn helper_refuses_brace_value() {
        // Values whose unparse starts with '{' are refused (Python ConversionRefused).
        let err = ast_formatted_value(name("{1: 2}"), None, None);
        assert!(matches!(err, Err(FlyntError::ConversionRefused(_))));
    }
}
