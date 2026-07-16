//! Port of src/flynt/linting/fstr_lint.py (FstrInliner).
//! Owner: task #4 (core utils).

use ruff_python_ast::Expr;

/// Inline nested f-strings inside a JoinedStr (Python: FstrInliner visitor).
pub fn inline_fstrings(node: &mut Expr) {
    let _ = node;
    todo!("task #4")
}
