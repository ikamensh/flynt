import ast
import io
import json
import re
import token
import tokenize


MOD_KEY_PATTERN = re.compile("(%\([^)]+\)s)")
MOD_KEY_NAME_PATTERN = re.compile("%\(([^)]+)\)s")
INDENT_PATTERN = re.compile("^(\ +)")
# VAR_KEY_PATTERN = re.compile("(%[a-z])")
VAR_KEY_PATTERN = re.compile("(%[sd])")

from fstringify.transform import fstringify_node


def dump_tokenize(code):
    try:
        g = tokenize.tokenize(io.BytesIO(code.encode("utf-8")).readline)
        for toknum, tokval, start, end, line in g:
            print(start, toknum, token.tok_name[toknum], tokval)

    except tokenize.TokenError:
        pass


def get_lines(code):

    lines = []
    last_line = None
    last_lineno = -1
    try:
        g = tokenize.tokenize(io.BytesIO(code.encode("utf-8")).readline)
        for toknum, tokval, start, end, line in g:
            # print(start, toknum, token.tok_name[toknum], tokval)

            lineno = start[0]

            if line != last_line and lineno != last_line and line:
                lines.append(line.rstrip())

            last_line = line
            last_lineno = lineno

    except tokenize.TokenError:
        pass

    return lines


def pp_code_ast(code, convert=False):
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


def get_indent(line):
    indented = INDENT_PATTERN.match(line)
    if indented:
        return indented[0]

    return ""


def trim_list(l):
    last = l.pop()
    l.pop()
    l.append(last)
    return l


def trim_list_until(l, length):
    if len(l) > 1 and length == 1:
        return [l[0]]

    while len(l) > length:
        l = trim_list(l)

    filler = l[-1] if l else ""
    while len(l) < length:
        l.append(filler)
    return l
