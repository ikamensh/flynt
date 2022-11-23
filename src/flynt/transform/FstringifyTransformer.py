import ast
from typing import Tuple

from flynt import state
from flynt.linting.fstr_lint import FstrInliner
from flynt.transform.format_call_transforms import joined_string, matching_call
from flynt.transform.percent_transformer import is_percent_stringify, transform_binop


class FstringifyTransformer(ast.NodeTransformer):
    def __init__(
        self,
        transform_percent: bool = True,
        transform_format: bool = True,
    ):
        super().__init__()
        self.counter = 0
        self.string_in_string = False
        self.transform_percent = transform_percent
        self.transform_format = transform_format

    def visit_Call(self, node: ast.Call):
        """
        Convert `ast.Call` to `ast.JoinedStr` f-string
        """

        if self.transform_format and matching_call(node):
            state.call_candidates += 1

            # bail in these edge cases...
            if any(isinstance(arg, ast.Starred) for arg in node.args):
                return node

            result_node, str_in_str = joined_string(node)
            self.string_in_string = str_in_str
            self.visit(result_node)
            self.counter += 1
            state.call_transforms += 1
            return result_node

        return node

    def visit_BinOp(self, node):
        """Convert `ast.BinOp` to `ast.JoinedStr` f-string

        Currently only if a string literal `ast.Str` is on the left side of the `%`
        and one of `ast.Tuple`, `ast.Name`, `ast.Dict` is on the right

        Args:
            node (ast.BinOp): The node to convert to a f-string

        Returns ast.JoinedStr (f-string)
        """

        if self.transform_percent and is_percent_stringify(node):
            state.percent_candidates += 1

            # bail in these edge cases...
            no_good = ["}", "{"]
            for ng in no_good:
                if ng in node.left.s:
                    return node
            for ch in ast.walk(node.right):
                # f-string expression part cannot include a backslash
                if isinstance(ch, ast.Str) and (
                    any(
                        map(
                            lambda x: x in ch.s,
                            ("\n", "\t", "\r", "'", '"', "%s", "%%"),
                        )
                    )
                    or "\\" in ch.s
                ):
                    return node

            result_node, str_in_str = transform_binop(node)
            self.string_in_string = str_in_str
            self.counter += 1
            state.percent_transforms += 1
            return result_node

        return node


def fstringify_node(
    node,
    transform_percent: bool = True,
    transform_format: bool = True,
) -> Tuple[ast.AST, bool, bool]:
    ft = FstringifyTransformer(
        transform_percent=transform_percent,
        transform_format=transform_format,
    )
    result = ft.visit(node)
    il = FstrInliner()
    il.visit(result)

    return result, ft.counter > 0, ft.string_in_string
