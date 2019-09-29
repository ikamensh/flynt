import ast
from typing import List

import astor

from flynt.format import QuoteTypes


def is_str_literal(node):
    """ Returns True if a node is a string literal """
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    else:
        return False


def is_str_compatible(node):
    """ Returns False if any nodes can't be a part of string concatenation """
    if is_str_literal(node):
        return True
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, ast.Add):
            return False
        else:
            return is_str_compatible(node.right) and is_str_compatible(node.left)
    elif isinstance(node, (ast.Name, ast.Call, ast.Subscript)):
        return True
    else:
        return False


def contains_literal(node):
    """ Returns true if a node or its BinOp children are string literals """
    if is_str_literal(node):
        return True
    elif isinstance(node, ast.BinOp):
        return contains_literal(node.left) or contains_literal(node.right)


def is_string_concat(node):
    """ Returns True for nodes representing a string concatenation """
    if not is_str_compatible(node):
        return False
    if not isinstance(node, ast.BinOp):
        return False
    return contains_literal(node)


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


def concat_candidates(code: str):
    tree = ast.parse(code)

    ch = ConcatHound()
    ch.visit(tree)

    yield from ch.victims
