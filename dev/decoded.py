# line: 1
import ast
# line: 3
with open('ast_example.py', 'r') as source, open('ast_example3.py', 'w'
    ) as source2:
    # line: 4
    tree = ast.parse(source.read())
# line: 7
import astor


# line: 9
def foo():
    # line: 10
    """ just incredible foonction """
    # line: 11
    pass


# line: 13
var = 12345
# line: 14
a = 'my string {}'.format(var)
# line: 15
b = f'my string {var}'
# line: 17
with open('decoded.py', 'w') as target:
    # line: 18
    txt = astor.to_source(tree, add_line_information=True)
    # line: 19
    target.write(txt)
