//! Port of src/flynt/transform/format_call_transforms.py.
//! Owner: task #6 (.format() pipeline).

use ruff_python_ast::Expr;

use crate::error::FlyntError;
use crate::state::State;

/// Port of matching_call + joined_string: convert `"...".format(...)` call
/// into an f-string expression.
pub fn transform_call(node: &Expr, state: &State) -> Result<Expr, FlyntError> {
    let _ = (node, state);
    todo!("task #6")
}
