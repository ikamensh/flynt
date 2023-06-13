import ast
from typing import List

from flynt.candidates.ast_chunk import AstChunk
from flynt.state import State
from flynt.static_join.utils import get_static_join_bits


class JoinHound(ast.NodeVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.victims: List[AstChunk] = []

    def visit_Call(self, node: ast.Call) -> None:
        """
        Finds all nodes that are joins with a static string literal
        as the joiner and a static iterable as the joinee.
        """
        if get_static_join_bits(node) is not None:
            self.victims.append(AstChunk(node))
        else:
            self.generic_visit(node)


def join_candidates(code: str, state: State):
    tree = ast.parse(code)

    ch = JoinHound()
    ch.visit(tree)

    state.join_candidates += len(ch.victims)

    return ch.victims
