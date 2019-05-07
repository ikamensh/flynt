from typing import List
import ast

#
# fstr = ast.JoinedStr([
#     ast.Str(s='my string '),
#     ast.FormattedValue(value=ast.Name(id='var'),
#                        conversion=-1,
#                        format_spec=None)
# ])
#
# import astor
# print(astor.to_source(fstr))


from collections import deque

def wrap_value( val ):
    return ast.FormattedValue(value=val,
                       conversion=-1,
                       format_spec=None)

def wrap_string( string ):
    return ast.Str(s=string)

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


parsed = ast.parse('a = "my string {}".format(var)')

assign = parsed.body[0]
# assign.value = f_stringify(assign.value)

import astor
print(astor.to_source(parsed))
