//! Port of src/flynt/string_concat/ (candidates.py, transformer.py,
//! string_in_string.py). Owner: task #8 (codex).

use ruff_python_ast::Expr;

use crate::chunk::Chunk;
use crate::quotes::QuoteType;
use crate::state::State;

/// Port of string_concat/candidates.py::concat_candidates.
pub fn concat_candidates(code: &str, state: &mut State) -> Vec<Chunk> {
    let _ = (code, state);
    todo!("task #8")
}

/// Port of string_concat/transformer.py::transform_concat.
pub fn transform_concat(node: &Expr, state: &mut State, quote_type: QuoteType) -> (String, bool) {
    let _ = (node, state, quote_type);
    todo!("task #8")
}
