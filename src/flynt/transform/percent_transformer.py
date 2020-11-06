import ast
import re
from collections import deque

from flynt.exceptions import FlyntException, ConversionRefused
from flynt.transform.format_call_transforms import ast_formatted_value, ast_string_node
from flynt import state

FORMATS = "diouxXeEfFgGcrsa"

FORMAT_GROUP = f"[hlL]?[{FORMATS}]"
FORMAT_GROUP_MATCH = f"[hlL]?([{FORMATS}])"

PREFIX_GROUP = "[0-9]*[.]?[0-9]*"

DICT_PATTERN = re.compile(rf"(%{PREFIX_GROUP}\([^)]+\){FORMAT_GROUP})")
SPLIT_DICT_PATTERN = re.compile(rf"%({PREFIX_GROUP})\(([^)]+)\){FORMAT_GROUP_MATCH}")
VAR_KEY_PATTERN = re.compile(
    f"%({PREFIX_GROUP}){FORMAT_GROUP_MATCH}"
)  # specs at https://docs.python.org/3/library/stdtypes.html#string-formatting
obsolete_specifiers = "hlL"

translate_conversion_types = {"i": "d", "u": "d"}
conversion_methods = {"r": "!r", "a": "!a", "s": None}
integer_specificers = 'dxXob'


def formatted_value(fmt_prefix, fmt_spec, val):
    if fmt_spec in integer_specificers:
        fmt_prefix = fmt_prefix.replace('.', '0')

    if fmt_spec in conversion_methods:
        if not state.aggressive and fmt_prefix:
            raise FlyntException(
                "Default text alignment has changed between percent fmt and fstrings. "
                "Proceeding would result in changed code behaviour."
            )
        fv = ast_formatted_value(
            val, fmt_str=fmt_prefix, conversion=conversion_methods[fmt_spec]
        )
    else:
        fmt_spec = translate_conversion_types.get(fmt_spec, fmt_spec)
        if fmt_spec == "d":
            if state.aggressive:
                val = ast.Call(
                    func=ast.Name(id="int", ctx=ast.Load()), args=[val], keywords={}
                )
                fmt_spec = ""
            else:
                raise FlyntException(
                    "Skipping %d formatting - fstrings behave differently from % formatting."
                )
        fv = ast_formatted_value(val, fmt_str=fmt_prefix + fmt_spec)
    return fv


def transform_dict(node):
    """Convert a `BinOp` `%` formatted str with a name representing a Dict on the right to an f-string.

    Takes an ast.BinOp representing `"1. %(key1)s 2. %(key2)s" % mydict`
    and converted it to a ast.JoinedStr representing `f"1. {mydict['key1']} 2. {mydict['key2']}"`

    Args:
       node (ast.BinOp): The node to convert to a f-string

    Returns ast.JoinedStr (f-string)
    """

    format_str = node.left.s
    matches = DICT_PATTERN.findall(format_str)
    spec = []
    for idx, m in enumerate(matches):
        _, prefix, var_key, fmt_str, _ = SPLIT_DICT_PATTERN.split(m)
        if not var_key:
            raise FlyntException("could not find dict key")
        spec.append((prefix, var_key, fmt_str))

    # build result node
    segments = []
    spec.reverse()
    blocks = DICT_PATTERN.split(format_str)

    mapping = {}
    if isinstance(node.right, ast.Dict):
        for k, v in zip(node.right.keys, node.right.values):
            mapping[str(ast.literal_eval(k))] = v

        def make_fv(key: str):
            return mapping.pop(key)

    else:

        def make_fv(key: str):
            return ast.Subscript(
                value=node.right, slice=ast.Index(value=ast.Str(s=key))
            )

    for block in blocks:
        # if this block matches a %(arg)s pattern then inject f-string instead
        if DICT_PATTERN.match(block):
            prefix, var_key, fmt_str = spec.pop()
            fv = formatted_value(prefix, fmt_str, make_fv(var_key))
            segments.append(fv)
        else:
            # no match means it's just a literal string
            segments.append(ast.Str(s=block.replace("%%", "%")))

    if mapping:
        raise FlyntException(
            "Not all keys were matched - either a flynt error or original code error."
        )

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
        raise ConversionRefused("This expression involves tuple unpacking.")

    str_vars = deque(node.right.elts)

    segments = []
    blocks = deque(VAR_KEY_PATTERN.split(format_str))
    segments.append(ast_string_node(blocks.popleft().replace("%%", "%")))

    while len(blocks) > 0:

        fmt_prefix = blocks.popleft()
        fmt_spec = blocks.popleft()
        val = str_vars.popleft()

        fv = formatted_value(fmt_prefix, fmt_spec, val)

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

    has_dict_str_format = DICT_PATTERN.findall(node.left.s)
    if has_dict_str_format:
        return transform_dict(node), True

    # if it's just a name then pretend it's tuple to use that code
    node.right = ast.Tuple(elts=[node.right])
    return transform_tuple(node), False


supported_operands = [
    ast.Name,
    ast.Attribute,
    ast.Str,
    ast.Subscript,
    ast.Call,
    ast.BinOp,
    ast.IfExp
]


def transform_binop(node):
    if isinstance(
        node.right,
        tuple(supported_operands),
    ):
        return transform_generic(node)

    elif isinstance(node.right, ast.Tuple):
        return transform_tuple(node), False

    elif isinstance(node.right, ast.Dict):
        # todo adapt transform dict to Dict literal
        return transform_dict(node), False

    raise ConversionRefused(f"Unsupported `node.right` class: {type(node.right)}")
