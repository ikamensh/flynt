"""Uses py3.8 AST to define a chunk of code as an AST node."""

import ast

import astor

from flynt.format import QuoteTypes


class AstChunk:
    def __init__(self, node: ast.AST):
        self.node = node

    @property
    def start_line(self):
        return self.node.lineno - 1

    @property
    def start_idx(self):
        return self.node.col_offset

    @property
    def end_idx(self):
        return self.node.end_col_offset

    @property
    def end_line(self):
        return self.node.end_lineno - 1

    @property
    def n_lines(self):
        return 1 + self.end_line - self.start_line

    @property
    def string_in_string(self):
        return False

    @property
    def quote_type(self):
        return QuoteTypes.double

    def __str__(self):
        return astor.to_source(self.node)[1:-2]

    def __repr__(self):
        return "AstChunk: " + str(self)
