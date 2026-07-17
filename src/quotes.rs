//! Port of src/flynt/utils/format.py — string quote detection and rewriting.
//!
//! Owner: task #4 (core utils). Implemented against test/test_styles.py.
//!
//! Everything operates on the *source text* of a string literal (quotes and
//! prefix included), exactly like the Python original — not on decoded values.

use crate::error::FlyntError;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum QuoteType {
    Single,
    Double,
    TripleSingle,
    TripleDouble,
}

/// Python: QuoteTypes.all order = [triple_double, triple_single, single, double]
pub const ALL_QUOTE_TYPES: [QuoteType; 4] = [
    QuoteType::TripleDouble,
    QuoteType::TripleSingle,
    QuoteType::Single,
    QuoteType::Double,
];

impl QuoteType {
    pub fn as_str(self) -> &'static str {
        match self {
            QuoteType::Single => "'",
            QuoteType::Double => "\"",
            QuoteType::TripleSingle => "'''",
            QuoteType::TripleDouble => "\"\"\"",
        }
    }
}

const PREFIX_CHARS: &[char] = &['f', 'u', 'r', 'b', 'F', 'U', 'R', 'B'];

/// Port of get_string_prefix: leading r/b/u/f chars of a string literal.
///
/// ```text
/// get_string_prefix("rb'x'") == "rb"
/// get_string_prefix("'x'")   == ""
/// ```
pub fn get_string_prefix(code: &str) -> String {
    let mut prefix = String::new();
    for ch in code.chars() {
        if PREFIX_CHARS.contains(&ch) {
            prefix.push(ch);
        } else {
            break;
        }
    }
    prefix
}

/// Port of get_quote_type. Returns the quote token used for `code`.
/// Errors (Python raises FlyntException) when no quote follows the prefix.
pub fn get_quote_type(code: &str) -> Result<QuoteType, FlyntError> {
    let prefix_len = get_string_prefix(code).len();
    let rest = &code[prefix_len..];
    // Alternation tries triple quotes before single (regex `['"]{3}|['"]`).
    if rest.starts_with("'''") {
        return Ok(QuoteType::TripleSingle);
    }
    if rest.starts_with("\"\"\"") {
        return Ok(QuoteType::TripleDouble);
    }
    if rest.starts_with('\'') {
        return Ok(QuoteType::Single);
    }
    if rest.starts_with('"') {
        return Ok(QuoteType::Double);
    }
    Err(FlyntError::Generic(format!(
        "Can't determine quote type of the string {code}."
    )))
}

/// Port of remove_quotes: strip the prefix and surrounding quotes, returning
/// the raw body. Not in the public Python API surface, but shared with
/// `astutils::unicode_escape_map`.
pub(crate) fn remove_quotes(code: &str) -> Result<String, FlyntError> {
    let prefix_len = get_string_prefix(code).len();
    let quote_len = get_quote_type(code)?.as_str().len();
    Ok(code[prefix_len + quote_len..code.len() - quote_len].to_string())
}

/// Replace every occurrence of `target` that is **not** immediately preceded by
/// a backslash with `\target`. Mirrors Python's `re.sub(r"(?<!\\)X", ...)`,
/// where the negative look-behind inspects only the single preceding character
/// of the *original* string.
fn escape_lonely(body: &str, target: char) -> String {
    let mut out = String::with_capacity(body.len());
    let mut prev: Option<char> = None;
    for ch in body.chars() {
        if ch == target && prev != Some('\\') {
            out.push('\\');
        }
        out.push(ch);
        prev = Some(ch);
    }
    out
}

/// Port of set_quote_type.
pub fn set_quote_type(code: &str, quote_type: QuoteType) -> String {
    let prefix = get_string_prefix(code);
    let has_f = prefix.chars().any(|c| c == 'f' || c == 'F');
    let other_prefix: String = prefix.chars().filter(|c| *c != 'f' && *c != 'F').collect();
    let mut body = remove_quotes(code).expect("set_quote_type: code must be a string literal");

    match quote_type {
        QuoteType::Single | QuoteType::TripleDouble => {
            if body.ends_with("\\\"") {
                // Trailing escaped double-quote `\"` -> `"`.
                let keep = body.len() - 2;
                body = format!("{}\"", &body[..keep]);
            }
        }
        QuoteType::Double => {
            body = escape_lonely(&body, '"');
        }
        QuoteType::TripleSingle => {}
    }

    if quote_type == QuoteType::Single {
        body = escape_lonely(&body, '\'');
    }

    let q = quote_type.as_str();
    let f = if has_f { "f" } else { "" };
    format!("{other_prefix}{f}{q}{body}{q}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn get_quote_type_basic() {
        assert_eq!(get_quote_type("'abra'").unwrap(), QuoteType::Single);
        assert_eq!(get_quote_type("\"bobro\"").unwrap(), QuoteType::Double);
        assert_eq!(
            get_quote_type("'''abra'''").unwrap(),
            QuoteType::TripleSingle
        );
        assert_eq!(
            get_quote_type("\"\"\"bobro\"\"\"").unwrap(),
            QuoteType::TripleDouble
        );
    }

    #[test]
    fn get_quote_type_with_prefix() {
        assert_eq!(get_quote_type("f'x'").unwrap(), QuoteType::Single);
        assert_eq!(get_quote_type("rb\"x\"").unwrap(), QuoteType::Double);
        assert_eq!(get_quote_type("F'''x'''").unwrap(), QuoteType::TripleSingle);
    }

    #[test]
    fn get_quote_type_no_quote_errors() {
        assert!(get_quote_type("abra").is_err());
    }

    #[test]
    fn string_prefix() {
        assert_eq!(get_string_prefix("rb'x'"), "rb");
        assert_eq!(get_string_prefix("'x'"), "");
        assert_eq!(get_string_prefix("Rf\"x\""), "Rf");
        assert_eq!(get_string_prefix("furb'x'"), "furb");
    }

    /// Property (test_cycle): round-tripping through the detected quote is identity.
    #[test]
    fn cycle_identity() {
        for code in ["'abra'", "\"bobro\"", "'''abra'''", "\"\"\"bobro\"\"\""] {
            assert_eq!(set_quote_type(code, get_quote_type(code).unwrap()), code);
        }
    }

    /// Property (test_initial_doesnt_matter): after set_quote_type, get_quote_type
    /// reports exactly what was set.
    #[test]
    fn set_then_get_roundtrip() {
        for code in ["'abra'", "\"bobro\"", "'''abra'''", "\"\"\"bobro\"\"\""] {
            for qt in ALL_QUOTE_TYPES {
                let converted = set_quote_type(code, qt);
                assert_eq!(
                    get_quote_type(&converted).unwrap(),
                    qt,
                    "code={code} qt={qt:?}"
                );
            }
        }
    }

    #[test]
    fn set_single() {
        assert_eq!(
            set_quote_type("\"alpha123\"", QuoteType::Single),
            "'alpha123'"
        );
    }

    #[test]
    fn set_single_from_triple() {
        assert_eq!(
            set_quote_type("\"\"\"alpha123\"\"\"", QuoteType::Single),
            "'alpha123'"
        );
    }

    #[test]
    fn escape_lonely_respects_backslash() {
        // Lone double quote gets escaped; already-escaped one is left alone.
        assert_eq!(escape_lonely("a\"b", '"'), "a\\\"b");
        assert_eq!(escape_lonely("a\\\"b", '"'), "a\\\"b");
    }
}
