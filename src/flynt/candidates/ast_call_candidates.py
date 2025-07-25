import ast
from typing import List

from flynt.state import State
from flynt.utils.utils import is_str_constant

from .ast_chunk import AstChunk


def is_call_format(node):
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
        # We only support literal format strings, not variables holding
        # format strings. `joined_string` will refuse non literals, but
        # filtering them here avoids unnecessary processing.
        and is_str_constant(node.func.value)
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
