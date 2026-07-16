//! Port of src/flynt/candidates/ast_call_candidates.py.
//! Owner: task #6 (.format() pipeline).

use crate::chunk::Chunk;
use crate::state::State;

/// Find `"...".format(...)` candidates; increments state.call_candidates.
pub fn call_candidates(code: &str, state: &mut State) -> Vec<Chunk> {
    let _ = (code, state);
    todo!("task #6")
}
