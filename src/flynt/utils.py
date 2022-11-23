import ast
from typing import Optional

import astor
from astor.string_repr import pretty_string

from flynt.exceptions import FlyntException
from flynt.format import QuoteTypes, set_quote_type
from flynt.linting.fstr_lint import FstrInliner


def nicer_pretty_string(
    s,
    embedded,
    current_line,
    uni_lit=False,
):
    r = repr(s)
    if "\\x" in r:
        # If the string contains an escape sequence,
        # we need to work around a bug in upstream astor;
        # the easiest workaround is to just use the repr
        # of the string and be done with it.
        return r
    return pretty_string(s, embedded, current_line, uni_lit=uni_lit)


def ast_to_string(node: ast.AST) -> str:
    # TODO: this could use `ast.unparse` when targeting Python 3.9+ only.
    return astor.to_source(node, pretty_string=nicer_pretty_string).rstrip()


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

    if ast_to_string(val).startswith("{"):
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


def fixup_transformed(tree: ast.AST, quote_type: Optional[str] = None) -> str:
    il = FstrInliner()
    il.visit(tree)
    new_code = ast_to_string(tree)
    if quote_type is None:
        if new_code[:4] == 'f"""' or new_code[:3] == "'''" or new_code[:3] == '"""':
            quote_type = QuoteTypes.double
    if quote_type is not None:
        new_code = set_quote_type(new_code, quote_type)
    new_code = new_code.replace("\n", "\\n")
    new_code = new_code.replace("\t", "\\t")
    return new_code
