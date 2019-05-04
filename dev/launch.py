from dev.traverse_ast import recursive_visit
import ast

parsed = ast.parse('a = "my string {}_{}".format(var1, var2)')

recursive_visit(parsed, 0)

import astor
print(asvtor.to_source(parsed))