import ast
from typing import List

from flynt.state import State

from .ast_chunk import AstChunk


def is_percent_format(node):
    return (
        isinstance(node, ast.BinOp)
        and isinstance(node.op, ast.Mod)
        and isinstance(node.left, ast.Str)
    )


class PercentFmtFinder(ast.NodeVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.candidates: List[AstChunk] = []

    def visit_BinOp(self, node: ast.BinOp) -> None:
        """
        Finds all nodes that are string concatenations with a literal.
        """
        if is_percent_format(node):
            self.candidates.append(AstChunk(node))
        else:
            self.generic_visit(node)


def percent_candidates(code: str, state: State) -> List[AstChunk]:
    tree = ast.parse(code)

    finder = PercentFmtFinder()
    finder.visit(tree)

    state.percent_candidates += len(finder.candidates)

    return finder.candidates
