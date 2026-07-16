//! Port of src/flynt/transform/ — the chunk-to-fstring transformation.
//!
//! `transform_chunk` is the single entry point used by CodeEditor for the
//! fstring pipeline (percent + format calls). It applies FstringifyTransformer
//! to the chunk's AST, unparses the result, and normalizes quotes.

pub mod format_call;
pub mod fstringify;
pub mod percent;

use ruff_python_ast::Expr;

use crate::quotes::QuoteType;
use crate::state::State;

/// Port of transform.transform_chunk: returns (converted_code, changed).
/// Increments state counters (percent_transforms / call_transforms /
/// invalid_conversions) exactly like the Python version.
/// Owner: task #6 (together with fstringify.rs orchestration).
pub fn transform_chunk(node: &Expr, state: &mut State, quote_type: QuoteType) -> (String, bool) {
    let _ = (node, state, quote_type);
    todo!("task #6")
}
