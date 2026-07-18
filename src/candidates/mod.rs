//! Candidate discovery. Each function parses `code` and returns candidate
//! chunks ordered by position (start of file to end, left to right) —
//! CodeEditor relies on this ordering.

pub mod call;
pub mod percent;

use crate::chunk::Chunk;
use crate::state::State;

/// Port of code_editor.fstring_candidates: percent + call candidates merged,
/// sorted by (start position).
pub fn fstring_candidates(code: &str, state: &mut State) -> Vec<Chunk> {
    let mut chunks = Vec::new();
    if state.transform_percent {
        chunks.extend(percent::percent_candidates(code, state));
    }
    if state.transform_format {
        chunks.extend(call::call_candidates(code, state));
    }
    chunks.sort_by_key(|c| c.range.start());
    chunks
}
