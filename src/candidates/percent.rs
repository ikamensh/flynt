//! Port of src/flynt/candidates/ast_percent_candidates.py.
//! Owner: task #5 (percent pipeline).

use crate::chunk::Chunk;
use crate::state::State;

/// Find `str % ...` candidates; increments state.percent_candidates.
pub fn percent_candidates(code: &str, state: &mut State) -> Vec<Chunk> {
    let _ = (code, state);
    todo!("task #5")
}
