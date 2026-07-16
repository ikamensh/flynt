//! Port of src/flynt/transform/percent_transformer.py.
//! Owner: task #5 (percent pipeline).

use ruff_python_ast::Expr;

use crate::error::FlyntError;
use crate::state::State;

/// Port of transform_binop: convert `left % right` BinOp into f-string parts.
/// Returns the JoinedStr-equivalent expression (ruff ExprFString).
pub fn transform_binop(node: &Expr, state: &State) -> Result<Expr, FlyntError> {
    let _ = (node, state);
    todo!("task #5")
}
