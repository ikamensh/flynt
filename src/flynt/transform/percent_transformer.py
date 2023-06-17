import ast
import re
from collections import deque
from typing import List, Union

from flynt.exceptions import ConversionRefused, FlyntException
from flynt.transform.format_call_transforms import ast_formatted_value, ast_string_node

FORMATS = "diouxXeEfFgGcrsa"

FORMAT_GROUP = f"[hlL]?[{FORMATS}]"
FORMAT_GROUP_MATCH = f"[hlL]?([{FORMATS}])"

PREFIX_GROUP = "[0-9]*[.]?[0-9]*"

ANY_DICT = re.compile(r"(?<!%)%\([^)]+?\)")
DICT_PATTERN = re.compile(rf"(%\([^)]+\){PREFIX_GROUP}{FORMAT_GROUP})")
SPLIT_DICT_PATTERN = re.compile(rf"%\(([^)]+)\)({PREFIX_GROUP}){FORMAT_GROUP_MATCH}")
VAR_KEY_PATTERN = re.compile(
    f"%({PREFIX_GROUP}){FORMAT_GROUP_MATCH}",
)  # specs at https://docs.python.org/3/library/stdtypes.html#string-formatting
obsolete_specifiers = "hlL"

translate_conversion_types = {"i": "d", "u": "d"}
conversion_methods = {"r": "!r", "a": "!a", "s": None}
integer_specificers = "dxXob"


def is_percent_stringify(node: ast.BinOp) -> bool:
    return (
        isinstance(node.left, ast.Str)
        and isinstance(node.op, ast.Mod)
        and isinstance(node.right, tuple([ast.Tuple, ast.Dict, *supported_operands]))
    )


def _is_len_call(val: ast.AST) -> bool:
    return (
        isinstance(val, ast.Call)
        and isinstance(val.func, ast.Name)
        and val.func.id == "len"
    )


def formatted_value(
    fmt_prefix: str,
    fmt_spec: str,
    val: ast.AST,
    *,
    aggressive: bool = False,
) -> Union[ast.FormattedValue, ast.Str]:
    if fmt_spec in integer_specificers:
        fmt_prefix = fmt_prefix.replace(".", "0")

    if fmt_spec in conversion_methods:
        if not aggressive and fmt_prefix:
            raise ConversionRefused(
                "Default text alignment has changed between percent fmt and fstrings. "
                "Proceeding would result in changed code behaviour.",
            )
        return ast_formatted_value(
            val,
            fmt_str=fmt_prefix,
            conversion=conversion_methods[fmt_spec],
        )
    fmt_spec = translate_conversion_types.get(fmt_spec, fmt_spec)
    if fmt_spec == "d":
        # assume built-in len always returns int
        if not _is_len_call(val):
            if not aggressive:
                raise ConversionRefused(
                    "Skipping %d formatting - fstrings behave differently from % formatting.",
                )
            val = ast.Call(
                func=ast.Name(id="int", ctx=ast.Load()),
                args=[val],
                keywords={},
            )
        fmt_spec = ""
    return ast_formatted_value(val, fmt_str=fmt_prefix + fmt_spec)


def transform_dict(node: ast.BinOp, aggressive: bool = False) -> ast.JoinedStr:
    """Convert a `BinOp` `%` formatted str with a name representing a Dict on the right to an f-string.

    Takes an ast.BinOp representing `"1. %(key1)s 2. %(key2)s" % mydict`
    and converted it to a ast.JoinedStr representing `f"1. {mydict['key1']} 2. {mydict['key2']}"`

    Args:
       node (ast.BinOp): The node to convert to a f-string

    Returns ast.JoinedStr (f-string)
    """
    assert isinstance(node.left, ast.Str)
    format_str = node.left.s
    matches = DICT_PATTERN.findall(format_str)
    if len(matches) != len(ANY_DICT.findall(format_str)):
        raise ConversionRefused("Some locations have unknown format modifiers.")

    spec = []
    for idx, m in enumerate(matches):
        _, var_key, prefix, fmt_str, _ = SPLIT_DICT_PATTERN.split(m)
        if not var_key:
            raise FlyntException("could not find dict key")
        spec.append((prefix, var_key, fmt_str))

    # build result node
    segments: List[ast.AST] = []
    spec.reverse()
    blocks = DICT_PATTERN.split(format_str)

    mapping = {}
    if isinstance(node.right, ast.Dict):
        for k, v in zip(node.right.keys, node.right.values):
            if k is not None:
                mapping[str(ast.literal_eval(k))] = v

        def make_fv(key: str):
            # only allow reused keys when aggressive is on
            return mapping[key] if aggressive else mapping.pop(key)

    else:

        def make_fv(key: str):
            return ast.Subscript(
                value=node.right,
                slice=ast.Index(value=ast.Str(s=key)),
            )

    for block in blocks:
        # if this block matches a %(arg)s pattern then inject f-string instead
        if DICT_PATTERN.match(block):
            prefix, var_key, fmt_str = spec.pop()
            fv = formatted_value(
                prefix,
                fmt_str,
                make_fv(var_key),
                aggressive=aggressive,
            )
            segments.append(fv)
        else:
            # no match means it's just a literal string
            segments.append(ast.Str(s=block.replace("%%", "%")))

    return ast.JoinedStr(segments)


def transform_tuple(node: ast.BinOp, *, aggressive: bool = False) -> ast.JoinedStr:
    """Convert a `BinOp` `%` formatted str with a tuple on the right to an f-string.

    Takes an ast.BinOp representing `"1. %s 2. %s" % (a, b)`
    and converted it to a ast.JoinedStr representing `f"1. {a} 2. {b}"`

    Args:
       node (ast.BinOp): The node to convert to a f-string

    Returns ast.JoinedStr (f-string)
    """
    assert isinstance(node.left, ast.Str)
    format_str = node.left.s
    matches = VAR_KEY_PATTERN.findall(format_str)

    assert isinstance(node.right, ast.Tuple)
    if len(node.right.elts) != len(matches):
        raise ConversionRefused("This expression involves tuple unpacking.")

    str_vars = deque(node.right.elts)

    segments: List[ast.AST] = []
    blocks = deque(VAR_KEY_PATTERN.split(format_str))
    segments.append(ast_string_node(blocks.popleft().replace("%%", "%")))

    while len(blocks) > 0:
        fmt_prefix = blocks.popleft()
        fmt_spec = blocks.popleft()
        val = str_vars.popleft()

        fv = formatted_value(fmt_prefix, fmt_spec, val, aggressive=aggressive)

        segments.append(fv)
        segments.append(ast_string_node(blocks.popleft().replace("%%", "%")))

    return ast.JoinedStr(segments)


def transform_generic(
    node: ast.BinOp,
    aggressive: bool = False,
) -> ast.JoinedStr:
    """Convert a `BinOp` `%` formatted str with a unknown name on the `node.right` to an f-string.

    When `node.right` is a Name since we don't know if it's a single var or a dict so we sniff the string.

    Sniffs the left string for Dict style usage
    e.g. `"val: %(key_name1)s val2: %(key_name2)s" % some_dict`

    else (e.g. `"val: %s" % some_var`):
    Borrow the core logic by injecting the name into a ast.Tuple

    Returns ast.JoinedStr (f-string), bool: str-in-str
    """
    assert isinstance(node.left, ast.Str)
    has_dict_str_format = DICT_PATTERN.findall(node.left.s)
    if has_dict_str_format:
        return transform_dict(node, aggressive=aggressive)

    any(isinstance(n, (ast.Str, ast.JoinedStr)) for n in ast.walk(node.right))

    # if it's just a name then pretend it's tuple to use that code
    node.right = ast.Tuple(elts=[node.right])
    return transform_tuple(node, aggressive=aggressive)


supported_operands = [
    ast.Name,
    ast.Attribute,
    ast.Str,
    ast.Subscript,
    ast.Call,
    ast.BinOp,
    ast.IfExp,
]


def transform_binop(
    node: ast.BinOp,
    *,
    aggressive: bool = False,
) -> ast.JoinedStr:
    if isinstance(node.right, tuple(supported_operands)):
        return transform_generic(node, aggressive=aggressive)

    if isinstance(node.right, ast.Tuple):
        return transform_tuple(node, aggressive=aggressive)

    if isinstance(node.right, ast.Dict):
        # todo adapt transform dict to Dict literal
        return transform_dict(node, aggressive=aggressive)

    raise ConversionRefused(f"Unsupported `node.right` class: {type(node.right)}")
