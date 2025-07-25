import ast
import string
from collections import deque
from typing import Any, Dict, List, Union

from flynt.exceptions import ConversionRefused, FlyntException
from flynt.utils.utils import (
    ast_formatted_value,
    ast_string_node,
    get_str_value,
    is_str_constant,
    is_str_literal,
)

stdlib_parse = string.Formatter().parse


def joined_string(
    fmt_call: ast.Call,
    *,
    aggressive: bool = False,
) -> Union[ast.JoinedStr, ast.Constant]:
    """Transform a "...".format() call node into a f-string node."""
    if not (
        isinstance(fmt_call.func, ast.Attribute)
        and is_str_constant(fmt_call.func.value)
    ):
        raise ConversionRefused("Only literal format strings are supported")

    string = get_str_value(fmt_call.func.value)
    var_map: Dict[Any, Any] = {kw.arg: kw.value for kw in fmt_call.keywords}
    inserted_value_nodes = []
    for a in fmt_call.args:
        inserted_value_nodes += list(ast.walk(a))
    for kw in fmt_call.keywords:
        inserted_value_nodes += list(ast.walk(kw.value))
    any(is_str_literal(n) for n in inserted_value_nodes)

    for i, val in enumerate(fmt_call.args):
        var_map[i] = val

    splits = deque(stdlib_parse(string))

    seq_ctr = 0
    new_segments: List[Union[ast.Constant, ast.FormattedValue]] = []
    manual_field_ordering = False

    for raw, var_name, fmt_str, conversion in splits:
        if raw:
            new_segments.append(ast_string_node(raw))

        if var_name is None:
            continue

        if "[" in var_name:
            raise FlyntException(
                f"Skipping f-stringify of a fmt call with indexed name {var_name}",
            )

        suffix = ""
        if "." in var_name:
            idx = var_name.find(".")
            var_name, suffix = var_name[:idx], var_name[idx + 1 :]

        identifier: Union[str, int]
        if var_name.isdigit():
            manual_field_ordering = True
            identifier = int(var_name)
        elif len(var_name) == 0:
            assert not manual_field_ordering
            identifier = seq_ctr
            seq_ctr += 1
        else:
            identifier = var_name

        if aggressive:
            ast_name = var_map[identifier]
        else:
            try:
                ast_name = var_map.pop(identifier)
            except KeyError as e:
                raise ConversionRefused(
                    f"A variable {identifier} is used multiple times - better not to replace it.",
                ) from e

        if suffix:
            ast_name = ast.Attribute(value=ast_name, attr=suffix)
        new_segments.append(ast_formatted_value(ast_name, fmt_str, conversion))

    if var_map and not aggressive:
        raise FlyntException(
            f"Some variables were never used: {var_map} - skipping conversion, it's a risk of bug.",
        )

    if all(is_str_constant(segment) for segment in new_segments):
        return ast.Constant(
            value="".join(get_str_value(segment) for segment in new_segments)
        )

    return ast.JoinedStr(new_segments)
