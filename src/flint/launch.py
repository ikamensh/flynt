import ast
import astor
from flint.crawler import recursive_visit


def flint_str(txt_in: str) -> str:
    """ compile txt_in as python source, and replace
    string format calls with f-string literals."""

    tree = ast.parse(txt_in)
    recursive_visit(tree, 0)
    return astor.to_source(tree)


def flint_file( filepath: str):
    with open(filepath, 'r') as f:
        txt_in = f.read()

    with open(filepath, 'w') as f:
        f.write(flint_str(txt_in))



