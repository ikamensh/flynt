//! Port of src/flynt/api.py. Owner: task #9.

use crate::state::State;

/// Result of converting one source string (Python: fstringify_code returns
/// Optional[...] with .content).
pub struct CodeResult {
    pub content: String,
    pub changes: usize,
}

/// Port of fstringify_code: run enabled pipelines over a code string.
/// Returns None when the source fails to parse (invalid Python).
pub fn fstringify_code(code: &str, state: &mut State, filename: &str) -> Option<CodeResult> {
    let _ = (code, state, filename);
    todo!("task #9")
}

/// Port of fstringify: resolve src paths, process files, print report;
/// returns the process exit code.
pub fn fstringify(
    src: &[String],
    excluded: Option<&[String]>,
    fail_on_changes: bool,
    state: &mut State,
) -> i32 {
    let _ = (src, excluded, fail_on_changes, state);
    todo!("task #9")
}
