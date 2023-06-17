import ast
import string
from collections import deque
from typing import Any, Dict, List, Union

from flynt.exceptions import ConversionRefused, FlyntException
from flynt.utils.utils import ast_formatted_value, ast_string_node

stdlib_parse = string.Formatter().parse


def joined_string(
    fmt_call: ast.Call,
    *,
    aggressive: bool = False,
) -> Union[ast.JoinedStr, ast.Str]:
    """Transform a "...".format() call node into a f-string node."""
    assert isinstance(fmt_call.func, ast.Attribute) and isinstance(
        fmt_call.func.value,
        ast.Str,
    )
    string = fmt_call.func.value.s
    var_map: Dict[Any, Any] = {kw.arg: kw.value for kw in fmt_call.keywords}
    inserted_value_nodes = []
    for a in fmt_call.args:
        inserted_value_nodes += list(ast.walk(a))
    for kw in fmt_call.keywords:
        inserted_value_nodes += list(ast.walk(kw.value))
    any(isinstance(n, (ast.Str, ast.JoinedStr)) for n in inserted_value_nodes)

    for i, val in enumerate(fmt_call.args):
        var_map[i] = val

    splits = deque(stdlib_parse(string))

    seq_ctr = 0
    new_segments: List[Union[ast.Str, ast.FormattedValue]] = []
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

    if all(isinstance(segment, ast.Str) for segment in new_segments):
        return ast.Str(
            "".join(segment.value for segment in new_segments)  # type:ignore[misc]
        )

    return ast.JoinedStr(new_segments)
