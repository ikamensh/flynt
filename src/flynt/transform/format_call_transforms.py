import ast
from collections import deque
import re

from flynt.exceptions import FlyntException

def ast_formatted_value(val, fmt_str: str = None, conversion = None) -> ast.FormattedValue:
    if fmt_str:
        format_spec = ast.JoinedStr([ast_string_node(fmt_str.replace(':', ''))])
    else:
        format_spec = None

    if conversion is None:
        conversion = -1
    else:
        conversion = ord(conversion.replace('!', ''))
    return ast.FormattedValue(value=val,
                       conversion=conversion,
                       format_spec=format_spec)

def ast_string_node(string: str) -> ast.Str:
    return ast.Str(s=string)

def matching_call(node) -> bool:
    """
    Check if a an ast Node represents a "...".format() call.
    """
    return (isinstance(node, ast.Call)
            and hasattr(node.func, 'value')
            and isinstance(node.func.value, ast.Str)
            and node.func.attr == "format")


def prep_var_map(keywords: list):
    var_map = {}
    for keyword in keywords:
        var_map[keyword.arg] = keyword.value

    return var_map

format_location_pattern = re.compile(r'{([a-zA-Z0-9_\[\]]*)(![rsa])?(:[.0-9a-z,%]*)?}(?!})')

def joined_string(fmt_call: ast.Call) -> ast.JoinedStr:
    """ Transform a "...".format() call node into a f-string node. """
    string = fmt_call.func.value.s
    values = deque(fmt_call.args)
    var_map = prep_var_map(fmt_call.keywords)

    splits = deque(format_location_pattern.split(string))

    new_segments = [ast_string_node(splits.popleft())]

    manual_field_ordering = False

    seen_varnames = set()

    while len(splits) > 0:
        var_name = splits.popleft()
        if var_name in seen_varnames:
            raise FlyntException("A variable is used multiple times - better not to replace it.")
        if var_name.isalnum():
            seen_varnames.add(var_name)

        if '[' in var_name:
            raise FlyntException(f"Skipping f-stringify of a fmt call with indexed name {var_name}")
        conversion = splits.popleft()
        fmt_str = splits.popleft()

        if var_name.isdigit():
            manual_field_ordering = True
            idx = int(var_name)
            new_segments.append(ast_formatted_value(values[idx], fmt_str, conversion))
        elif len(var_name) == 0:
            assert not manual_field_ordering
            new_segments.append(ast_formatted_value(values.popleft(), fmt_str, conversion))
        else:
            new_segments.append(ast_formatted_value(var_map[var_name], fmt_str, conversion))

        new_segments.append(ast_string_node(splits.popleft()))

    if values and not manual_field_ordering:
        raise FlyntException("Mismatch between the number of formatting locations and provided variables")

    return ast.JoinedStr(new_segments)