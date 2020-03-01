import ast
from typing import List

from flynt.ast_chunk import AstChunk


class FstringFinder(ast.NodeVisitor):
    def __init__(self):
        super().__init__()
        self.victims: List[AstChunk] = []

    def visit_JoinedStr(self, node: ast.BinOp):
        """
        Finds all nodes that are string concatenations with a literal
        """
        self.victims.append(AstChunk(node))


def fstr_candidates(code: str):
    tree = ast.parse(code)

    ch = FstringFinder()
    ch.visit(tree)

    yield from ch.victims


class FstrInliner(ast.NodeTransformer):
    def visit_JoinedStr(self, node):
        new_vals = []
        for v in node.values:
            if (
                isinstance(v, ast.FormattedValue)
                and isinstance(v.value, ast.JoinedStr)
                and v.format_spec is None
            ):
                new_vals += v.value.values
            else:
                new_vals.append(v)

        node.values = new_vals
        return self.generic_visit(node)
