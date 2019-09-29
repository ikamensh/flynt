import ast
from typing import List, Tuple

import astor

from flynt.exceptions import FlyntException


def ast_formatted_value(
    val, fmt_str: str = None, conversion=None
) -> ast.FormattedValue:

    if astor.to_source(val)[0] == "{":
        raise FlyntException(
            "values starting with '{' are better left not transformed."
        )

    if fmt_str:
        format_spec = ast.JoinedStr([ast_string_node(fmt_str.replace(":", ""))])
    else:
        format_spec = None

    if conversion is None:
        conversion = -1
    else:
        conversion = ord(conversion.replace("!", ""))
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


class FstringifyTransformer(ast.NodeTransformer):
    def __init__(self):
        super().__init__()
        self.counter = 0

    def visit_BinOp(self, node: ast.BinOp):
        """
        Transforms a string concat to an f-string
        """
        self.counter += 1
        pieces = unpack_binop(node)

        segments = []
        for p in pieces:
            if isinstance(p, ast.Constant):
                segments.append(ast_string_node(p.value))
            else:
                segments.append(ast_formatted_value(p))

        return ast.JoinedStr(segments)


from flynt.format import QuoteTypes, set_quote_type


def transform_concat(code: str, *args, **kwargs) -> Tuple[str, bool]:
    tree = ast.parse(code)

    ft = FstringifyTransformer()
    ft.visit(tree)

    new_code = astor.to_source(tree)
    if new_code[-1] == "\n":
        new_code = new_code[:-1]
    new_code = set_quote_type(new_code, QuoteTypes.double)

    return new_code, ft.counter > 0
