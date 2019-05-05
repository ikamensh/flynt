import ast

from fstringify.utils import pp_ast, pp_code_ast

with open("ast_example.py", "r") as source:
    tree = ast.parse(source.read())

pp_ast(tree)

#small comment
import astor

def foo():
    """ just incredible foonction """
    pass

var = 12345
a = "my string {}".format(var)
b = f"my string {var}"

with open("decoded.py", 'w') as target:
    txt = astor.to_source(tree, add_line_information=True)
    target.write(txt)





