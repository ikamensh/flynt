import ast
from typing import Tuple

from flynt.static_join.utils import get_static_join_bits
from flynt.utils import ast_formatted_value, ast_string_node, fixup_transformed


class JoinTransformer(ast.NodeTransformer):
    def __init__(self):
        super().__init__()
        self.counter = 0

    def visit_Call(self, node: ast.Call):
        """
        Transforms a static string join to an f-string.
        """
        res = get_static_join_bits(node)
        if not res:
            return self.generic_visit(node)
        joiner, args = res
        self.counter += 1
        args_with_interleaved_joiner = []
        for arg in args:
            if isinstance(arg, ast.Str):
                args_with_interleaved_joiner.append(arg)
            else:
                args_with_interleaved_joiner.append(ast_formatted_value(arg))
            args_with_interleaved_joiner.append(ast_string_node(joiner))
        args_with_interleaved_joiner.pop()  # remove the last joiner
        if all(isinstance(arg, ast.Str) for arg in args_with_interleaved_joiner):
            return ast.Str(s="".join(arg.s for arg in args_with_interleaved_joiner))
        return ast.JoinedStr(args_with_interleaved_joiner)


def transform_join(code: str, *args, **kwargs) -> Tuple[str, bool]:
    tree = ast.parse(f"({code})")

    jt = JoinTransformer()
    jt.visit(tree)
    new_code = fixup_transformed(tree)
    return new_code, jt.counter > 0
