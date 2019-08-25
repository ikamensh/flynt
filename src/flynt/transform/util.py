import ast
import json


def pp_code_ast(code, convert=False):
    from flynt.transform.transform import fstringify_node

    """Pretty print code's AST to stdout.

    Args:
        code (str): The code you want the ast for.

    Returns nothing print AST representation to stdout
    """
    tree = ast.parse(code)
    if convert:
        tree, _ = fstringify_node(tree)
    pp_ast(tree)


def _get_classname(cls):
    return cls.__class__.__name__


def ast_to_dict(node):
    """Convert an AST node to a dictionary for debugging.

    This is mainly for powering `pp_ast` (pretty printing).

    derived from `jsonify_ast` here:
    https://github.com/maligree/python-ast-explorer/blob/master/parse.py#L7

    Args:
       node (AST): the ast to turn into debug dict


    Returns a dictionary.
    """
    if not node:
        return None
    fields = {}
    for key in node._fields:
        if not hasattr(node, key):
            continue
        value = getattr(node, key)
        if isinstance(value, ast.AST):
            if value._fields:
                fields[key] = ast_to_dict(value)
            else:
                fields[key] = _get_classname(value)

        elif isinstance(value, list):
            fields[key] = []
            for element in value:
                fields[key].append(ast_to_dict(element))

        elif isinstance(value, (str, int, float)):
            fields[key] = value

        elif value is None:
            fields[key] = None

        else:
            fields[key] = str(value)

    return {_get_classname(node): fields}


def pp_ast(node):
    """Pretty print an AST to stdout"""
    print(json.dumps(ast_to_dict(node), indent=2))
