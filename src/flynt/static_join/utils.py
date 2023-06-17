import ast
from typing import List, Optional, Sequence, Tuple

from flynt.utils.utils import is_str_literal


def get_joiner_from_static_join(func: ast.AST) -> Optional[str]:
    if (
        isinstance(func, ast.Attribute)
        and func.attr == "join"
        and is_str_literal(func.value)
    ):
        return ast.literal_eval(func.value)
    return None


def get_arguments_from_static_join(args: Sequence[ast.AST]) -> Optional[List[ast.AST]]:
    if len(args) == 1 and isinstance(args[0], (ast.List, ast.Tuple, ast.Set)):
        elts: List[ast.AST] = list(args[0].elts)
        if any(isinstance(elt, ast.Starred) for elt in elts):
            # If there's a `*starred` element in the list, it's not valid.
            return None
        return elts
    return None


def get_static_join_bits(node: ast.Call) -> Optional[Tuple[str, List[ast.AST]]]:
    joiner = get_joiner_from_static_join(node.func)
    if joiner is None:
        return None
    args = get_arguments_from_static_join(node.args)
    if args is None:
        return None
    return joiner, args
