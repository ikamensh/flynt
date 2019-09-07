import ast
from collections import deque

from flynt.transform.format_call_transforms import ast_string_node, ast_formatted_value
from flynt.exceptions import FlyntException

import re

MOD_KEY_PATTERN = re.compile(r"(%\([^)]+\)s)")
MOD_KEY_NAME_PATTERN = re.compile(r"%\(([^)]+)\)s")
VAR_KEY_PATTERN = re.compile(
    "%([.]?[0-9]*)[hlL]?([diouxXeEfFgGcrsa])"
)  # specs at https://docs.python.org/3/library/stdtypes.html#string-formatting
obsolete_specifiers = "hlL"

translate_conversion_types = {"i": "d", "u": "d"}
conversion_methods = {"r": "!r", "a": "!a", "s": None}


def transform_dict(node):
    """Convert a `BinOp` `%` formatted str with a name representing a Dict on the right to an f-string.

    Takes an ast.BinOp representing `"1. %(key1)s 2. %(key2)s" % mydict`
    and converted it to a ast.JoinedStr representing `f"1. {mydict['key1']} 2. {mydict['key2']}"`

    Args:
       node (ast.BinOp): The node to convert to a f-string

    Returns ast.JoinedStr (f-string)
    """

    format_str = node.left.s
    matches = MOD_KEY_PATTERN.findall(format_str)
    var_keys = []
    for idx, m in enumerate(matches):
        var_key = MOD_KEY_NAME_PATTERN.match(m)
        if not var_key:
            raise FlyntException("could not find dict key")
        var_keys.append(var_key[1])

    # build result node
    segments = []
    var_keys.reverse()
    blocks = MOD_KEY_PATTERN.split(format_str)
    for block in blocks:
        # if this block matches a %(arg)s pattern then inject f-string instead
        if MOD_KEY_PATTERN.match(block):
            fv = ast.FormattedValue(
                value=ast.Subscript(
                    value=node.right, slice=ast.Index(value=ast.Str(s=var_keys.pop()))
                ),
                conversion=-1,
                format_spec=None,
            )

            segments.append(fv)
        else:
            # no match means it's just a literal string
            segments.append(ast.Str(s=block.replace("%%", "%")))
    return ast.JoinedStr(segments)


def transform_tuple(node):
    """Convert a `BinOp` `%` formatted str with a tuple on the right to an f-string.

    Takes an ast.BinOp representing `"1. %s 2. %s" % (a, b)`
    and converted it to a ast.JoinedStr representing `f"1. {a} 2. {b}"`

    Args:
       node (ast.BinOp): The node to convert to a f-string

    Returns ast.JoinedStr (f-string)
    """

    format_str = node.left.s
    matches = VAR_KEY_PATTERN.findall(format_str)

    if len(node.right.elts) != len(matches):
        raise FlyntException("string formatting length mismatch")

    str_vars = deque(node.right.elts)

    segments = []
    blocks = deque(VAR_KEY_PATTERN.split(format_str))
    segments.append(ast_string_node(blocks.popleft().replace("%%", "%")))

    while len(blocks) > 0:

        fmt_prefix = blocks.popleft()
        fmt_spec = blocks.popleft()
        for c in obsolete_specifiers:
            fmt_spec = fmt_spec.replace(c, "")

        if fmt_spec in conversion_methods:
            if fmt_prefix:
                raise FlyntException(
                    "Default text alignment has changed between percent fmt and fstrings. "
                    "Proceeding would result in changed code behaviour."
                )
            fv = ast_formatted_value(
                str_vars.popleft(),
                fmt_str=fmt_prefix,
                conversion=conversion_methods[fmt_spec],
            )
        else:
            fmt_spec = translate_conversion_types.get(fmt_spec, fmt_spec)
            fv = ast_formatted_value(str_vars.popleft(), fmt_str=fmt_prefix + fmt_spec)

        segments.append(fv)
        segments.append(ast_string_node(blocks.popleft().replace("%%", "%")))

    return ast.JoinedStr(segments)


def transform_generic(node):
    """Convert a `BinOp` `%` formatted str with a unknown name on the `node.right` to an f-string.

    When `node.right` is a Name since we don't know if it's a single var or a dict so we sniff the string.

    Sniffs the left string for Dict style usage
    e.g. `"val: %(key_name1)s val2: %(key_name2)s" % some_dict`

    else (e.g. `"val: %s" % some_var`):
    Borrow the core logic by injecting the name into a ast.Tuple

    Returns ast.JoinedStr (f-string), bool: str-in-str
    """

    has_dict_str_format = MOD_KEY_PATTERN.findall(node.left.s)
    if has_dict_str_format:
        return transform_dict(node), True

    # if it's just a name then pretend it's tuple to use that code
    node.right = ast.Tuple(elts=[node.right])
    return transform_tuple(node), False


def transform_binop(node):
    if isinstance(
        node.right, (ast.Name, ast.Attribute, ast.Str, ast.BinOp, ast.Subscript)
    ):
        return transform_generic(node)

    elif isinstance(node.right, ast.Tuple):
        return transform_tuple(node), False

    elif isinstance(node.right, ast.Dict):
        # todo adapt transform dict to Dict literal
        return transform_dict(node), False

    raise FlyntException("unexpected `node.right` class")
