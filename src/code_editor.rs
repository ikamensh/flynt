//! Port of src/flynt/code_editor.py. Owner: task #7.
//!
//! CodeEditor applies local edits while keeping the rest of the original
//! source byte-for-byte. See the Python docstring for the invariants;
//! candidates arrive ordered first-to-last.

use ruff_python_ast::Expr;

use crate::chunk::Chunk;
use crate::quotes::QuoteType;
use crate::state::State;

/// The transform callback shape shared by all three pipelines:
/// (node, state, quote_type) -> (converted_source, changed).
pub type TransformFunc = fn(&Expr, &mut State, QuoteType) -> (String, bool);

/// Candidate discovery callback: code + state -> ordered chunks.
pub type CandidatesFunc = fn(&str, &mut State) -> Vec<Chunk>;

/// Port of fstringify_code_by_line: returns (new_code, count_of_edits).
pub fn fstringify_code_by_line(code: &str, state: &mut State) -> (String, usize) {
    let _ = (code, state);
    todo!("task #7")
}

/// Port of fstringify_concats.
pub fn fstringify_concats(code: &str, state: &mut State) -> (String, usize) {
    let _ = (code, state);
    todo!("task #7")
}

/// Port of fstringify_static_joins.
pub fn fstringify_static_joins(code: &str, state: &mut State) -> (String, usize) {
    let _ = (code, state);
    todo!("task #7")
}
