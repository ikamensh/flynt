import ast
from collections import deque

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
    return {kw.arg: kw.value for kw in keywords}

import string
stdlib_parse = string.Formatter().parse

def joined_string(fmt_call: ast.Call) -> ast.JoinedStr:
    """ Transform a "...".format() call node into a f-string node. """
    string = fmt_call.func.value.s
    var_map = prep_var_map(fmt_call.keywords)

    for i, val in enumerate(fmt_call.args):
        var_map[i] = val

    splits = deque(stdlib_parse(string))

    seen_varnames = set()
    seq_ctr = 0
    new_segments = []
    manual_field_ordering = False


    for raw, var_name, fmt_str, conversion in splits:
        if raw:
            new_segments.append( ast_string_node(raw) )


        if var_name in seen_varnames:
            raise FlyntException("A variable is used multiple times - better not to replace it.")

        if var_name is None:
            continue
        elif var_name != '':
            seen_varnames.add(var_name)

        if '[' in var_name:
            raise FlyntException(f"Skipping f-stringify of a fmt call with indexed name {var_name}")

        if var_name.isdigit():
            manual_field_ordering = True
            idx = int(var_name)
            new_segments.append(ast_formatted_value(var_map[idx], fmt_str, conversion))
        elif len(var_name) == 0:
            assert not manual_field_ordering
            new_segments.append(ast_formatted_value(var_map[seq_ctr], fmt_str, conversion))
            seq_ctr += 1
        else:
            new_segments.append(ast_formatted_value(var_map[var_name], fmt_str, conversion))

    return ast.JoinedStr(new_segments)