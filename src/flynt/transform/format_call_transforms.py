import ast
from collections import deque
import string

from flynt.exceptions import FlyntException


def ast_formatted_value(
    val, fmt_str: str = None, conversion=None
) -> ast.FormattedValue:
    if fmt_str:
        format_spec = ast.JoinedStr([ast_string_node(fmt_str.replace(":", ""))])
    else:
        format_spec = None

    if conversion is None:
        conversion = -1
    else:
        conversion = ord(conversion.replace("!", ""))
    return ast.FormattedValue(value=val, conversion=conversion, format_spec=format_spec)


def ast_string_node(ast_str: str) -> ast.Str:
    return ast.Str(s=ast_str)


def matching_call(node) -> bool:
    """
    Check if a an ast Node represents a "...".format() call.
    """
    return (
        isinstance(node, ast.Call)
        and hasattr(node.func, "value")
        and isinstance(node.func.value, ast.Str)
        and node.func.attr == "format"
    )


stdlib_parse = string.Formatter().parse


def joined_string(fmt_call: ast.Call) -> ast.JoinedStr:
    """ Transform a "...".format() call node into a f-string node. """
    var_map = {kw.arg: kw.value for kw in fmt_call.keywords}

    for i, val in enumerate(fmt_call.args):
        var_map[i] = val

    splits = deque(stdlib_parse(fmt_call.func.value.s))

    seq_ctr = 0
    new_segments = []
    manual_field_ordering = False

    for raw, var_name, fmt_str, conversion in splits:
        if raw:
            new_segments.append(ast_string_node(raw))

        if var_name is None:
            continue

        if "[" in var_name:
            raise FlyntException(
                f"Skipping f-stringify of a fmt call with indexed name {var_name}"
            )

        suffix = ""
        if "." in var_name:
            idx = var_name.find(".")
            var_name, suffix = var_name[:idx], var_name[idx + 1 :]

        if var_name.isdigit():
            manual_field_ordering = True
            identifier = int(var_name)
        elif not var_name:
            assert not manual_field_ordering
            identifier = seq_ctr
            seq_ctr += 1
        else:
            identifier = var_name

        try:
            ast_name = var_map.pop(identifier)
            if suffix:
                ast_name = ast.Attribute(value=ast_name, attr=suffix)
            new_segments.append(ast_formatted_value(ast_name, fmt_str, conversion))
        except IndexError as e:
            raise FlyntException(
                "A variable is used multiple times - better not to replace it."
            ) from e

    if var_map:
        raise FlyntException("A variable was never used - a risk of bug.")

    return ast.JoinedStr(new_segments)
