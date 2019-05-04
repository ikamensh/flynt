import ast
import astor
from typing import Tuple
from flint.crawler import recursive_visit


def flint_str(txt_in: str) -> Tuple[str, int]:
    """ compile txt_in as python source, and replace
    string format calls with f-string literals.

    Return the new string and the number of replacements made."""

    tree = ast.parse(txt_in)
    count = recursive_visit(tree, 0)
    return astor.to_source(tree), count


def flint_file( filepath: str):
    with open(filepath, 'r') as f:
        txt_in = f.read()

    with open(filepath, 'w') as f:
        txt_out, count = flint_str(txt_in)
        f.write(txt_out)

    print(f"{count} replacements made on {filepath}")



