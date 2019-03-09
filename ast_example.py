import ast

with open("ast_example.py", "r") as source, open("ast_example3.py", "w") as source2:
    tree = ast.parse(source.read())

#small comment
import astor

def foo():
    """ just incredible foonction """
    pass

var = 12345
"my string {}".format(var)
f"my string {var}"

with open("decoded.py", 'w') as target:
    txt = astor.to_source(tree, add_line_information=True)
    target.write(txt)




