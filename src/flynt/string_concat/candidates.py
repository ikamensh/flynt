import ast
from typing import List

import astor

from flynt.format import QuoteTypes
from flynt import state


def is_str_literal(node):
    """ Returns True if a node is a string literal """
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    elif isinstance(node, ast.JoinedStr):
        return True
    else:
        return False


def is_string_concat(node):
    """ Returns True for nodes representing a string concatenation """
    if is_str_literal(node):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return is_string_concat(node.left) or is_string_concat(node.right)
    return False


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


class ConcatHound(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        self.victims: List[AstChunk] = []

    def visit_BinOp(self, node: ast.BinOp):
        """
        Finds all nodes that are string concatenations with a literal
        """
        if is_string_concat(node):
            self.victims.append(AstChunk(node))
        else:
            self.generic_visit(node)


def concat_candidates(code: str):
    tree = ast.parse(code)

    ch = ConcatHound()
    ch.visit(tree)

    state.concat_candidates += len(ch.victims)

    yield from ch.victims
