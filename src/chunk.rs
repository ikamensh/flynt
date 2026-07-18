//! Port of src/flynt/candidates/ast_chunk.py.
//!
//! A candidate site in the source: an owned AST expression plus its byte
//! range in the original source. Python flynt stores (lineno, col_offset)
//! pairs where col offsets are utf-8 *byte* offsets; ruff gives us a byte
//! `TextRange` directly, and `LineIndex` recovers line/col when needed.

use ruff_python_ast::Expr;
use ruff_text_size::TextRange;

#[derive(Debug, Clone)]
pub struct Chunk {
    /// Owned (cloned) expression subtree for this candidate.
    pub node: Expr,
    /// Byte range of the candidate in the original source.
    pub range: TextRange,
}

impl Chunk {
    pub fn new(node: Expr, range: TextRange) -> Self {
        Self { node, range }
    }
}

/// Sort candidates into source order and drop same-range duplicates.
///
/// ruff 0.14.11's `walk_stmt` visits an `elif` clause's test expression twice
/// (once inline in the `StmtIf` arm, once more via `walk_elif_else_clause`),
/// so a candidate inside an `elif` condition gets collected twice — and a
/// double-applied edit duplicates the replacement text in the output. An
/// identical range is by construction the same node, so deduping is safe for
/// every collector.
pub fn sort_dedup(chunks: &mut Vec<Chunk>) {
    chunks.sort_by_key(|c| (c.range.start(), c.range.end()));
    chunks.dedup_by_key(|c| c.range);
}
