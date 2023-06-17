import ast
from typing import Iterable, List

from flynt.candidates.ast_chunk import AstChunk
from flynt.state import State
from flynt.utils.utils import is_str_literal


def is_string_concat(node: ast.AST) -> bool:
    """Returns True for nodes representing a string concatenation."""
    if is_str_literal(node):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return is_string_concat(node.left) or is_string_concat(node.right)
    return False


class ConcatHound(ast.NodeVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.victims: List[AstChunk] = []

    def visit_BinOp(self, node: ast.BinOp) -> None:
        """
        Finds all nodes that are string concatenations with a literal.
        """
        if is_string_concat(node):
            self.victims.append(AstChunk(node))
        else:
            self.generic_visit(node)


def concat_candidates(code: str, state: State) -> Iterable[AstChunk]:
    tree = ast.parse(code)

    ch = ConcatHound()
    ch.visit(tree)

    state.concat_candidates += len(ch.victims)

    return ch.victims
