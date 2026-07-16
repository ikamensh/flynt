//! Port of src/flynt/transform/FstringifyTransformer.py + transform.py glue.
//! Owner: task #6.

use ruff_python_ast::Expr;

use crate::error::FlyntError;
use crate::state::State;

/// Port of fstringify_node: walk the expression, applying percent and
/// format-call transforms; returns (new_node, changed).
pub fn fstringify_node(node: &Expr, state: &mut State) -> Result<(Expr, bool), FlyntError> {
    let _ = (node, state);
    todo!("task #6")
}
