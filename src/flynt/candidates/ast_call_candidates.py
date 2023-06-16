import ast
from typing import List

from flynt.state import State

from .ast_chunk import AstChunk


def is_call_format(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
        and isinstance(node.func.value, (ast.Str, ast.Name))
    )


class CallFmtFinder(ast.NodeVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.candidates: List[AstChunk] = []

    def visit_Call(self, node: ast.Call) -> None:
        """
        Finds all nodes that are string concatenations with a literal.
        """
        if is_call_format(node):
            self.candidates.append(AstChunk(node))
        else:
            self.generic_visit(node)


def call_candidates(code: str, state: State) -> List[AstChunk]:
    tree = ast.parse(code)

    finder = CallFmtFinder()
    finder.visit(tree)

    state.call_candidates += len(finder.candidates)
    return finder.candidates
