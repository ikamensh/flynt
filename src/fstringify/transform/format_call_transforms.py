import ast
from collections import deque
import re
def ast_formatted_value(val, fmt_str: str) -> ast.FormattedValue:
    format_spec = None if len(fmt_str) == 0 else ast.JoinedStr([ast_string_node(fmt_str)])
    return ast.FormattedValue(value=val,
                       conversion=-1,
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


def joined_string(fmt_call: ast.Call) -> ast.JoinedStr:
    """ Transform a "...".format() call node into a f-string node. """
    string = fmt_call.func.value.s
    values = deque(fmt_call.args)
    var_map = prep_var_map(fmt_call.keywords)
    pat = re.compile(r'{([a-zA-Z0-9_]*):*([.0-9a-z]*)}')

    splits = deque( pat.split(string) )

    new_segments = [ast_string_node(splits.popleft())]

    while len(splits) > 0:
        var_name = splits.popleft()
        fmt_str = splits.popleft()

        if len(var_name) == 0:
            new_segments.append(ast_formatted_value(values.popleft(), fmt_str))
        else:
            new_segments.append(ast_formatted_value(var_map[var_name], fmt_str))

        new_segments.append(ast_string_node(splits.popleft()))


    return ast.JoinedStr(new_segments)