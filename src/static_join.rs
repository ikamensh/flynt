//! Port of src/flynt/static_join/ (candidates.py, transformer.py, utils.py).
//! Owner: task #8 (codex).

use ruff_python_ast::Expr;

use crate::chunk::Chunk;
use crate::quotes::QuoteType;
use crate::state::State;

/// Port of static_join/candidates.py::join_candidates.
pub fn join_candidates(code: &str, state: &mut State) -> Vec<Chunk> {
    let _ = (code, state);
    todo!("task #8")
}

/// Port of static_join/transformer.py::transform_join.
pub fn transform_join(node: &Expr, state: &mut State, quote_type: QuoteType) -> (String, bool) {
    let _ = (node, state, quote_type);
    todo!("task #8")
}
