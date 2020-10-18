import ast
from typing import List, Tuple

import astor

from flynt.exceptions import FlyntException
from flynt.format import QuoteTypes, set_quote_type
from flynt.string_concat.candidates import is_string_concat
from flynt.string_concat.string_in_string import check_sns_depth
from flynt.linting.fstr_lint import FstrInliner


def ast_formatted_value(
    val, fmt_str: str = None, conversion=None
) -> ast.FormattedValue:
    if isinstance(val, ast.FormattedValue):
        return val

    if astor.to_source(val)[0] == "{":
        raise FlyntException(
            "values starting with '{' are better left not transformed."
        )

    if fmt_str:
        format_spec = ast.JoinedStr([ast_string_node(fmt_str.replace(":", ""))])
    else:
        format_spec = None

    conversion = -1 if conversion is None else ord(conversion.replace("!", ""))
    return ast.FormattedValue(value=val, conversion=conversion, format_spec=format_spec)


def ast_string_node(string: str) -> ast.Str:
    return ast.Str(s=string)


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
    il = FstrInliner()
    il.visit(tree)

    new_code = astor.to_source(tree)
    if new_code[-1] == "\n":
        new_code = new_code[:-1]

    new_code = new_code.replace("\n", "\\n")
    if new_code[:4] == 'f"""':
        new_code = set_quote_type(new_code, QuoteTypes.double)

    return new_code, ft.counter > 0
