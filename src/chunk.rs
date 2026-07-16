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
