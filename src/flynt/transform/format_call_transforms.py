import ast
import sys
import string
from collections import deque
from typing import Tuple, Union

from flynt import state
from flynt.exceptions import FlyntException, ConversionRefused
from flynt.utils import ast_formatted_value, ast_string_node


def matching_call(node) -> bool:
    """
    Check if an ast Node represents a "...".format() call.
    """
    call_from_string = (
        isinstance(node.func, ast.Attribute)
        and hasattr(node.func, "value")
        and (
            isinstance(node.func.value, ast.Str)
            or (
                isinstance(node.func.value, ast.Constant)
                and isinstance(node.func.value.value, str)
            )
        )
    )
    return (
        isinstance(node, ast.Call) and call_from_string and node.func.attr == "format"
    )


stdlib_parse = string.Formatter().parse


def joined_string(fmt_call: ast.Call) -> Tuple[Union[ast.JoinedStr, ast.Str], bool]:
    """Transform a "...".format() call node into a f-string node."""

    string = fmt_call.func.value.s
    var_map = {kw.arg: kw.value for kw in fmt_call.keywords}
    inserted_value_nodes = []
    for a in fmt_call.args:
        inserted_value_nodes += list(ast.walk(a))
    for kw in fmt_call.keywords:
        inserted_value_nodes += list(ast.walk(kw.value))
    str_in_str = any(
        isinstance(n, (ast.Str, ast.JoinedStr)) for n in inserted_value_nodes
    )

    for i, val in enumerate(fmt_call.args):
        var_map[i] = val

    splits = deque(stdlib_parse(string))

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
        elif len(var_name) == 0:
            assert not manual_field_ordering
            identifier = seq_ctr
            seq_ctr += 1
        else:
            identifier = var_name

        if state.aggressive:
            ast_name = var_map[identifier]
        else:
            try:

                ast_name = var_map.pop(identifier)
            except KeyError as e:
                raise ConversionRefused(
                    f"A variable {identifier} is used multiple times - better not to replace it."
                ) from e

        if suffix:
            ast_name = ast.Attribute(value=ast_name, attr=suffix)
        new_segments.append(ast_formatted_value(ast_name, fmt_str, conversion))

    if var_map and not state.aggressive:
        raise FlyntException(
            f"Some variables were never used: {var_map} - skipping conversion, it's a risk of bug."
        )

    def is_literal_string(node):
        if sys.version_info < (3, 8):
            return isinstance(node, ast.Str)
        else:
            return isinstance(node, ast.Constant) and isinstance(node.value, str)

    def literal_string_value(node):
        if sys.version_info < (3, 8):
            return node.s
        else:
            return node.value

    def fix_literals(segment):
        if (
            isinstance(segment, ast.FormattedValue)
            and segment.format_spec is None
            and is_literal_string(segment.value)
        ):
            return segment.value
        return segment

    new_segments = [fix_literals(e) for e in new_segments]

    if all(is_literal_string(segment) for segment in new_segments):
        return (
            ast.Str("".join(literal_string_value(segment) for segment in new_segments)),
            False,
        )

    return ast.JoinedStr(new_segments), str_in_str
