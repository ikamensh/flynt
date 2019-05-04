import ast
from collections import deque

def wrap_value( val ):
    return ast.FormattedValue(value=val,
                       conversion=-1,
                       format_spec=None)

def wrap_string( string ):
    return ast.Str(s=string)

def matching_call(node):
    return (isinstance(node, ast.Call)
            and hasattr(node.func, 'value')
            and isinstance(node.func.value, ast.Str)
            and node.func.attr == "format")


def f_stringify(fmt_call: ast.Call):
    string = fmt_call.func.value.s
    values = deque(fmt_call.args)

    splits = deque( string.split('{}') )

    new_segments = [wrap_string(splits.popleft())]

    while values:
        new_segments.append( wrap_value(values.popleft()) )
        try:
            new_segments.append( wrap_string(splits.popleft()) )
        except:
            pass

    return ast.JoinedStr(new_segments)


if __name__ == "__main__":
    parsed = ast.parse('a = "my string {}".format(var)')

    assign = parsed.body[0]
    print(matching_call(assign.value))
    print(matching_call(assign))
    assign.value = f_stringify(assign.value)

    import astor
    print(astor.to_source(parsed))
