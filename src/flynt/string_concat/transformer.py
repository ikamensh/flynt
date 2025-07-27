import ast
from typing import List, Tuple

from flynt.exceptions import ConversionRefused
from flynt.string_concat.candidates import is_string_concat
from flynt.string_concat.string_in_string import check_sns_depth
from flynt.utils.format import QuoteTypes
from flynt.utils.utils import (
    ast_formatted_value,
    ast_string_node,
    fixup_transformed,
    get_str_value,
)


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
    def __init__(self) -> None:
        super().__init__()
        self.counter = 0

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
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

        segments: List[ast.AST] = []
        for p in parts:
            if isinstance(p, ast.Constant):
                segments.append(ast_string_node(p.value))
            else:
                segments.append(ast_formatted_value(p))

        if all(isinstance(p, ast.Constant) for p in segments):
            return ast.Constant(value="".join(get_str_value(p) for p in segments))

        return ast.JoinedStr(segments)


def transform_concat(tree: ast.AST, *args, **kwargs) -> Tuple[str, bool]:
    ft = ConcatTransformer()
    new = ft.visit(tree)
    changed = ft.counter > 0
    if changed:
        qt = None
        target = new
        if (
            isinstance(new, ast.Module)
            and len(new.body) == 1
            and isinstance(new.body[0], ast.Expr)
        ):
            target = new.body[0].value
        if isinstance(target, (ast.JoinedStr, ast.Constant)):
            qt = QuoteTypes.double
        try:
            new_code = fixup_transformed(new, quote_type=qt)
        except (ValueError, ConversionRefused):
            return "", False
    else:
        new_code = ""
    return new_code, changed
