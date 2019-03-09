import ast

minus_five = ast.UnaryOp(ast.USub(), ast.Num(5, lineno=0, col_offset=0),
                         lineno=0, col_offset=0)

import astor


print(astor.to_source(minus_five))





import ast

fstr = ast.JoinedStr([
    ast.Str(s='my string '),
    ast.FormattedValue(value=ast.Name(id='var'))
])

import astor


print(astor.to_source(fstr))