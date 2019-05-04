# line: 1
import ast
# line: 3
from fstringify.utils import pp_ast, pp_code_ast
# line: 5
with open('ast_example.py', 'r') as source:
    # line: 6
    tree = ast.parse(source.read())
# line: 8
pp_ast(tree)
# line: 11
import astor


# line: 13
def foo():
    # line: 14
    """ just incredible foonction """
    # line: 15
    pass


# line: 17
var = 12345
# line: 18
a = 'my string {}'.format(var)
# line: 19
b = f'my string {var}'
# line: 21
with open('decoded.py', 'w') as target:
    # line: 22
    txt = astor.to_source(tree, add_line_information=True)
    # line: 23
    target.write(txt)
