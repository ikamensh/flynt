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
    classname = lambda cls: cls.__class__.__name__
    for k in node._fields:
        if not hasattr(node, k):
            continue
        v = getattr(node, k)
        if isinstance(v, ast.AST):
            if v._fields:
                fields[k] = ast_to_dict(v)
            else:
                fields[k] = classname(v)

        elif isinstance(v, list):
            fields[k] = []
            for e in v:
                fields[k].append(ast_to_dict(e))

        elif isinstance(v, (str, int, float)):
            fields[k] = v

        elif v is None:
            fields[k] = None

        else:
            fields[k] = str(v)

    return {classname(node): fields}

def pp_ast(node):
    """Pretty print an AST to stdout"""
    print(json.dumps(ast_to_dict(node), indent=2))