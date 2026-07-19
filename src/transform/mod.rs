//! Port of src/flynt/transform/ — the chunk-to-fstring transformation.
//!
//! `transform_chunk` is the single entry point used by CodeEditor for the
//! fstring pipeline (percent + format calls). It applies FstringifyTransformer
//! to the chunk's AST, unparses the result, and normalizes quotes.

pub mod format_call;
pub mod fstringify;
pub mod percent;

use ruff_python_ast::Expr;

use crate::astutils::{fixup_transformed, str_in_str};
use crate::quotes::QuoteType;
use crate::state::State;

/// Port of `transform.transform_chunk`: returns `(converted_code, changed)`.
///
/// Runs `fstringify_node` on a deep copy of the candidate, unparses via
/// `fixup_transformed`, and validates that the generated snippet re-parses.
/// Any refusal/exception, or an unparseable result, increments
/// `state.invalid_conversions` and yields `("", false)` (Python's `(None,
/// False)`). Length limits are applied later by `CodeEditor`, not here.
pub fn transform_chunk(node: &Expr, state: &mut State, quote_type: QuoteType) -> (String, bool) {
    let (converted, changed) = match fstringify::fstringify_node(node, state) {
        Ok(v) => v,
        // ConversionRefused and every other error collapse to the same
        // observable result; the reason surfaces as a -v diagnostic.
        Err(e) => {
            state.invalid_conversions += 1;
            state.pend_reason(e.reason());
            return (String::new(), false);
        }
    };

    if !changed {
        return (String::new(), false);
    }

    // When an embedded string forces double quotes, upgrade single -> double.
    let mut qt = quote_type;
    if quote_type == QuoteType::Single && str_in_str(&converted) {
        qt = QuoteType::Double;
    }

    let new_code = match fixup_transformed(converted, Some(qt)) {
        Ok(c) => c,
        Err(e) => {
            state.invalid_conversions += 1;
            state.pend_reason(e.reason());
            return (String::new(), false);
        }
    };

    // Safety: the generated snippet must be valid Python (Python: `ast.parse`).
    if ruff_python_parser::parse_module(&new_code).is_err() {
        state.invalid_conversions += 1;
        state.pend_reason("conversion produced invalid code; not converted");
        return (String::new(), false);
    }

    (new_code, true)
}
