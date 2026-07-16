//! Port of src/flynt/utils/utils.py — AST helpers and the unparser wrapper.
//!
//! Owner: task #4 (core utils).
//!
//! Contract notes:
//! - `unparse_expr` must match CPython `ast.unparse` output on the expression
//!   subset flynt emits (the golden files pin the exact text). Use
//!   `ruff_python_codegen::Generator` with defaults matching ast.unparse
//!   (single-quote preference, no line wrapping) and patch any differences.
//! - `ast_to_string` additionally strips redundant parens around ternaries
//!   inside f-string replacement fields (see Python impl regex).

use ruff_python_ast::Expr;

use crate::error::FlyntError;

/// Port of ast_to_string (ast.unparse + ternary-paren cleanup).
pub fn ast_to_string(node: &Expr) -> Result<String, FlyntError> {
    let _ = node;
    todo!("task #4")
}

/// Port of str_in_str: true if a formatted value contains a string constant
/// or nested JoinedStr (used to refuse unsafe conversions pre-3.12 style).
pub fn str_in_str(node: &Expr) -> bool {
    let _ = node;
    todo!("task #4")
}

/// Port of contains_comment: does this code snippet contain a `#` comment
/// outside of string literals? (Python impl tokenizes.)
pub fn contains_comment(code: &str) -> bool {
    let _ = code;
    todo!("task #4")
}

/// Port of unicode_escape_map: map of escaped unicode sequences (\N{...},
/// \u..., \x...) appearing in the snippet, keyed by their decoded form.
pub fn unicode_escape_map(code: &str) -> Result<std::collections::HashMap<String, String>, FlyntError> {
    let _ = code;
    todo!("task #4")
}

/// Port of apply_unicode_escape_map.
pub fn apply_unicode_escape_map(code: &str, map: &std::collections::HashMap<String, String>) -> String {
    let _ = (code, map);
    todo!("task #4")
}
