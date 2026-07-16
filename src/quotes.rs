//! Port of src/flynt/utils/format.py — string quote detection and rewriting.
//!
//! Owner: task #4 (core utils). Implement against test/test_styles.py.

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

/// Port of get_string_prefix: leading r/b/u/f chars of a string literal.
pub fn get_string_prefix(code: &str) -> String {
    todo!("task #4: port get_string_prefix from utils/format.py")
}

/// Port of get_quote_type.
pub fn get_quote_type(code: &str) -> Result<QuoteType, FlyntError> {
    let _ = code;
    todo!("task #4: port get_quote_type from utils/format.py")
}

/// Port of set_quote_type.
pub fn set_quote_type(code: &str, quote_type: QuoteType) -> String {
    let _ = (code, quote_type);
    todo!("task #4: port set_quote_type from utils/format.py")
}
