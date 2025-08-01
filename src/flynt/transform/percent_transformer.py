import ast
import re
from collections import deque
from typing import List, Union

from flynt.exceptions import ConversionRefused, FlyntException
from flynt.transform.format_call_transforms import ast_formatted_value, ast_string_node
from flynt.utils.utils import get_str_value, is_str_constant

FORMATS = "diouxXeEfFgGcrsa"

FORMAT_GROUP = f"[hlL]?[{FORMATS}]"
FORMAT_GROUP_MATCH = f"[hlL]?([{FORMATS}])"

PREFIX_GROUP = "[+-]?[0-9]*[.]?[0-9]*"

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
        is_str_constant(node.left)
        and isinstance(node.op, ast.Mod)
        and isinstance(
            node.right, tuple([ast.Tuple, ast.List, ast.Dict, *supported_operands])
        )
    )


def _is_builtin_int_call(val: ast.AST) -> bool:
    return _is_int_call(val) or _is_len_call(val)


def _is_int_call(val: ast.AST) -> bool:
    return (
        isinstance(val, ast.Call)
        and isinstance(val.func, ast.Name)
        and val.func.id == "int"
    )


def _is_len_call(val: ast.AST) -> bool:
    # assume built-in len always returns int
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
    aggressive: int = 0,
) -> Union[ast.FormattedValue, ast.Constant]:
    if fmt_spec in integer_specificers:
        fmt_prefix = fmt_prefix.replace(".", "0")

    if fmt_spec in conversion_methods:
        if fmt_spec == "s" and fmt_prefix:
            # Strings are right aligned in percent fmt by default, and indicate
            # left alignment through a negative prefix.
            #
            # fstrings left align by default, and separate signs from alignment
            #
            # Python even accepts float values here, for both percent fmt
            # and fstrings
            #
            # In order to not have to figure out what sort of number we are
            # dealing with, just look at the leading - sign (if there is one)
            # and remove it for the conversion
            if fmt_prefix.startswith("-"):
                # Left alignment
                return ast_formatted_value(
                    val,
                    fmt_str=f"{fmt_prefix[1:]}",
                    conversion=conversion_methods[fmt_spec],
                )
            if aggressive >= 1 and not fmt_prefix.startswith("-"):
                # Right alignment
                return ast_formatted_value(
                    val,
                    fmt_str=f">{fmt_prefix}",
                    conversion=conversion_methods[fmt_spec],
                )
        if aggressive < 1 and fmt_prefix:
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
        # test if is a built-in that returns int
        if not _is_builtin_int_call(val):
            if aggressive < 1:
                raise ConversionRefused(
                    "Skipping %d formatting - fstrings behave differently from % formatting.",
                )
            if aggressive < 2:
                val = ast.Call(
                    func=ast.Name(id="int", ctx=ast.Load()),
                    args=[val],
                    keywords={},
                )
        fmt_spec = ""
    return ast_formatted_value(val, fmt_str=fmt_prefix + fmt_spec)


def transform_dict(node: ast.BinOp, aggressive: int = 0) -> ast.JoinedStr:
    """Convert a `BinOp` `%` formatted str with a name representing a Dict on the right to an f-string.

    Takes an ast.BinOp representing `"1. %(key1)s 2. %(key2)s" % mydict`
    and converted it to a ast.JoinedStr representing `f"1. {mydict['key1']} 2. {mydict['key2']}"`

    Args:
       node (ast.BinOp): The node to convert to a f-string

    Returns ast.JoinedStr (f-string)
    """
    assert is_str_constant(node.left)
    format_str = get_str_value(node.left)
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
                slice=ast.Index(value=ast.Constant(value=key)),
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
            segments.append(ast_string_node(block.replace("%%", "%")))

    return ast.JoinedStr(segments)


def transform_tuple(node: ast.BinOp, *, aggressive: int = 0) -> ast.JoinedStr:
    """Convert a `BinOp` `%` formatted str with a tuple on the right to an f-string.

    Takes an ast.BinOp representing `"1. %s 2. %s" % (a, b)`
    and converted it to a ast.JoinedStr representing `f"1. {a} 2. {b}"`

    Args:
       node (ast.BinOp): The node to convert to a f-string

    Returns ast.JoinedStr (f-string)
    """
    assert is_str_constant(node.left)
    format_str = get_str_value(node.left)
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


def transform_list(node: ast.BinOp, *, aggressive: int = 0) -> ast.JoinedStr:
    """Convert a `BinOp` `%` formatted str with a list on the right to an f-string.

    Takes an ast.BinOp representing `"1. %s 2. %s" % [a, b]`
    and converted it to a ast.JoinedStr representing `f"1. {a} 2. {b}"`
    Borrow the core logic by converting the list into a ast.Tuple

    Args:
       node (ast.BinOp): The node to convert to a f-string

    Returns ast.JoinedStr (f-string)
    """
    assert isinstance(node.right, ast.List)

    # convert the list to a tuple to use that code
    node.right = ast.Tuple(elts=node.right.elts)
    return transform_tuple(node, aggressive=aggressive)


def transform_generic(node: ast.BinOp, aggressive: int = 0) -> ast.JoinedStr:
    """Convert a `BinOp` `%` formatted str with a unknown name on the `node.right` to an f-string.

    When `node.right` is a Name since we don't know if it's a single var or a dict so we sniff the string.

    Sniffs the left string for Dict style usage
    e.g. `"val: %(key_name1)s val2: %(key_name2)s" % some_dict`

    else (e.g. `"val: %s" % some_var`):
    Borrow the core logic by injecting the name into a ast.Tuple

    Returns ast.JoinedStr (f-string), bool: str-in-str
    """
    assert is_str_constant(node.left)
    has_dict_str_format = DICT_PATTERN.findall(get_str_value(node.left))
    if has_dict_str_format:
        return transform_dict(node, aggressive=aggressive)

    # if it's just a name then pretend it's tuple to use that code
    node.right = ast.Tuple(elts=[node.right])
    return transform_tuple(node, aggressive=aggressive)


supported_operands = [
    ast.Name,
    ast.Attribute,
    ast.Constant,
    ast.Subscript,
    ast.Call,
    ast.BinOp,
    ast.IfExp,
]


def transform_binop(node: ast.BinOp, *, aggressive: int = 0) -> ast.JoinedStr:
    if isinstance(node.right, tuple(supported_operands)):
        return transform_generic(node, aggressive=aggressive)

    if isinstance(node.right, ast.Tuple):
        return transform_tuple(node, aggressive=aggressive)

    if isinstance(node.right, ast.List):
        return transform_list(node, aggressive=aggressive)

    if isinstance(node.right, ast.Dict):
        # todo adapt transform dict to Dict literal
        return transform_dict(node, aggressive=aggressive)

    raise ConversionRefused(f"Unsupported `node.right` class: {type(node.right)}")
