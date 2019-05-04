import ast
from collections import deque
import re
def wrap_value( val ):
    return ast.FormattedValue(value=val,
                       conversion=-1,
                       format_spec=None)

def wrap_string( string ):
    return ast.Str(s=string)

def matching_call(node):
    """
    Check is node is a Call node representing string format.
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


def f_stringify(fmt_call: ast.Call):
    string = fmt_call.func.value.s
    values = deque(fmt_call.args)
    var_map = prep_var_map(fmt_call.keywords)
    pat = re.compile(r'{([a-zA-Z0-9_]*)}')

    splits = deque( pat.split(string) )

    new_segments = [wrap_string(splits.popleft())]

    while len(splits) > 0:
        var_name = splits.popleft()

        if len(var_name) == 0:
            new_segments.append( wrap_value(values.popleft()) )
        else:
            new_segments.append( wrap_value(var_map[var_name]) )

        new_segments.append(wrap_string(splits.popleft()))

    return ast.JoinedStr(new_segments)