import ast
from typing import Tuple

from flynt.candidates.ast_call_candidates import is_call_format
from flynt.linting.fstr_lint import FstrInliner
from flynt.state import State
from flynt.transform.format_call_transforms import joined_string
from flynt.transform.percent_transformer import is_percent_stringify, transform_binop


class FstringifyTransformer(ast.NodeTransformer):
    def __init__(
        self,
        state: State,
    ) -> None:
        super().__init__()
        self.state = state
        self.counter = 0

    def visit_Call(self, node: ast.Call) -> ast.AST:
        """
        Convert `ast.Call` to `ast.JoinedStr` f-string.
        """
        if self.state.transform_format and is_call_format(node):
            self.state.call_candidates += 1

            # bail in these edge cases...
            if any(isinstance(arg, ast.Starred) for arg in node.args):
                return node

            result_node = joined_string(
                node,
                aggressive=self.state.aggressive,
            )
            self.visit(result_node)
            self.counter += 1
            self.state.call_transforms += 1
            return result_node

        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        """Convert `ast.BinOp` to `ast.JoinedStr` f-string.

        Currently only if a string literal `ast.Str` is on the left side of the `%`
        and one of `ast.Tuple`, `ast.Name`, `ast.Dict` is on the right

        Args:
            node (ast.BinOp): The node to convert to a f-string

        Returns ast.JoinedStr (f-string)
        """
        if self.state.transform_percent and is_percent_stringify(node):
            # Mypy doesn't understand the is_percent_stringify acts
            # as a type guard, so we need the assert here.
            assert isinstance(node.left, ast.Str)
            self.state.percent_candidates += 1

            # bail in these edge cases...
            no_good = ["}", "{"]
            for ng in no_good:
                if ng in node.left.s:
                    return node
            for ch in ast.walk(node.right):
                # f-string expression part cannot include a backslash
                if isinstance(ch, ast.Str) and (
                    any(x in ch.s for x in ("\n", "\t", "\r", "'", '"', "%s", "%%"))
                    or "\\" in ch.s
                ):
                    return node

            result_node = transform_binop(
                node,
                aggressive=self.state.aggressive,
            )
            self.counter += 1
            self.state.percent_transforms += 1
            return result_node

        return node


def fstringify_node(
    node: ast.AST,
    state: State,
) -> Tuple[ast.AST, bool]:
    ft = FstringifyTransformer(state)
    result = ft.visit(node)
    il = FstrInliner()
    il.visit(result)

    return result, ft.counter > 0
