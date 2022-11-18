import ast
from typing import Optional

import astor

from flynt.exceptions import FlyntException
from flynt.format import set_quote_type, QuoteTypes
from flynt.linting.fstr_lint import FstrInliner


def is_str_literal(node):
    """Returns True if a node is a string literal. f-string is also a string literal."""
    return isinstance(node, (ast.Str, ast.JoinedStr))


def ast_formatted_value(
    val: ast.AST,
    fmt_str: str = None,
    conversion: Optional[str] = None,
) -> ast.FormattedValue:
    if isinstance(val, ast.FormattedValue):
        return val

    if astor.to_source(val)[0] == "{":
        raise FlyntException(
            "values starting with '{' are better left not transformed."
        )

    if fmt_str:
        format_spec = ast.JoinedStr([ast_string_node(fmt_str)])
    else:
        format_spec = None

    conversion = -1 if conversion is None else ord(conversion.replace("!", ""))
    return ast.FormattedValue(value=val, conversion=conversion, format_spec=format_spec)


def ast_string_node(string: str) -> ast.Str:
    return ast.Str(s=string)


def fixup_transformed(tree: ast.AST) -> str:
    il = FstrInliner()
    il.visit(tree)
    new_code = astor.to_source(tree)
    if new_code[-1] == "\n":
        new_code = new_code[:-1]
    new_code = new_code.replace("\n", "\\n")
    if new_code[:4] == 'f"""' or new_code[:3] == "'''" or new_code[:3] == '"""':
        new_code = set_quote_type(new_code, QuoteTypes.double)
    return new_code
