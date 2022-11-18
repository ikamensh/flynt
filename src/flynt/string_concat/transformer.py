import ast
from typing import List, Tuple

from flynt.string_concat.candidates import is_string_concat
from flynt.string_concat.string_in_string import check_sns_depth
from flynt.utils import ast_formatted_value, ast_string_node, fixup_transformed


def unpack_binop(node: ast.BinOp) -> List[ast.AST]:
    assert isinstance(node, ast.BinOp)
    result = []

    if isinstance(node.left, ast.BinOp):
        result.extend(unpack_binop(node.left))
    else:
        result.append(node.left)

    if isinstance(node.right, ast.BinOp):
        result.extend(unpack_binop(node.right))
    else:
        result.append(node.right)

    return result


class ConcatTransformer(ast.NodeTransformer):
    def __init__(self):
        super().__init__()
        self.counter = 0

    def visit_BinOp(self, node: ast.BinOp):
        """
        Transforms a string concat to an f-string
        """
        if not is_string_concat(node):
            return self.generic_visit(node)
        self.counter += 1
        left, right = node.left, node.right
        left = self.visit(left)
        right = self.visit(right)

        if not check_sns_depth(left) or not check_sns_depth(right):
            node.left = left
            node.right = right
            return node

        parts = []
        for p in [left, right]:
            if isinstance(p, ast.JoinedStr):
                parts += p.values
            else:
                parts.append(p)

        segments = []
        for p in parts:
            if isinstance(p, ast.Constant):
                segments.append(ast_string_node(p.value))
            else:
                segments.append(ast_formatted_value(p))

        return ast.JoinedStr(segments)


def transform_concat(code: str, *args, **kwargs) -> Tuple[str, bool]:
    tree = ast.parse(f"({code})")

    ft = ConcatTransformer()
    ft.visit(tree)
    new_code = fixup_transformed(tree)

    return new_code, ft.counter > 0
