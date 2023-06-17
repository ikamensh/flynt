"""Uses py3.8 AST to define a chunk of code as an AST node."""

import ast


class AstChunk:
    def __init__(self, node: ast.AST) -> None:
        self.node = node

    @property
    def start_line(self) -> int:
        return self.node.lineno - 1

    @property
    def start_idx(self) -> int:
        return self.node.col_offset

    @property
    def end_idx(self) -> int:
        idx = self.node.end_col_offset
        assert idx is not None
        return idx

    @property
    def end_line(self) -> int:
        lineno = self.node.end_lineno
        assert lineno is not None
        return lineno - 1

    @property
    def n_lines(self) -> int:
        return 1 + self.end_line - self.start_line

    @property
    def quote_type(self) -> str:
        raise NotImplementedError

    def __str__(self) -> str:
        from flynt.utils.utils import ast_to_string

        src = ast_to_string(self.node)
        if src.startswith("(") and src.endswith(")"):
            src = src[1:-1]
        return src

    def __repr__(self) -> str:
        return f"AstChunk: {self}"
