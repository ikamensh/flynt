import ast
from collections import deque
import re

from flynt.transform.format_call_transforms import (
    matching_call,
    ast_string_node,
    joined_string,
    ast_formatted_value,
)
from flynt.exceptions import FlyntException

MOD_KEY_PATTERN = re.compile(r"(%\([^)]+\)s)")
MOD_KEY_NAME_PATTERN = re.compile(r"%\(([^)]+)\)s")
VAR_KEY_PATTERN = re.compile(
    "%([.]?[0-9]*)[hlL]?([diouxXeEfFgGcrsa])"
)  # specs at https://docs.python.org/3/library/stdtypes.html#string-formatting
OBSOLETE_SPECIFIERS = "hlL"


TRANSLATE_CONVERSION_TYPES = {"i": "d", "u": "d"}
CONVERSION_METHODS = {"r": "!r", "a": "!a", "s": None}


def handle_from_mod_dict_name(node):
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
    for _, match in enumerate(matches):
        var_key = MOD_KEY_NAME_PATTERN.match(match)
        if not var_key:
            raise FlyntException("could not find dict key")
        var_keys.append(var_key[1])

    # build result node
    result_node = ast.JoinedStr()
    result_node.values = []
    var_keys.reverse()
    blocks = MOD_KEY_PATTERN.split(format_str)
    # loop through the blocks of a string to build up dateh JoinStr.values
    for block in blocks:
        # if this block matches a %(arg)s pattern then inject f-string instead
        if MOD_KEY_PATTERN.match(block):
            formatted_value = ast.FormattedValue(
                value=ast.Subscript(
                    value=node.right, slice=ast.Index(value=ast.Str(s=var_keys.pop()))
                ),
                conversion=-1,
                format_spec=None,
            )

            result_node.values.append(formatted_value)
        else:
            # no match means it's just a literal string
            result_node.values.append(ast.Str(s=block))
    return result_node


def handle_from_mod_tuple(node):
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

    # build result node
    result_node = ast.JoinedStr()
    result_node.values = []
    blocks = deque(VAR_KEY_PATTERN.split(format_str))
    result_node.values.append(ast_string_node(blocks.popleft()))

    while blocks:

        fmt_prefix = blocks.popleft()
        fmt_spec = blocks.popleft()
        for char in OBSOLETE_SPECIFIERS:
            fmt_spec = fmt_spec.replace(char, "")

        if fmt_spec in CONVERSION_METHODS:
            if fmt_prefix:
                raise FlyntException(
                    "Default text alignment has changed between percent fmt and fstrings. "
                    "Proceeding would result in changed code behaviour."
                )
            formatted_value = ast_formatted_value(
                str_vars.popleft(),
                fmt_str=fmt_prefix,
                conversion=CONVERSION_METHODS[fmt_spec],
            )
        else:
            fmt_spec = TRANSLATE_CONVERSION_TYPES.get(fmt_spec, fmt_spec)
            formatted_value = ast_formatted_value(
                str_vars.popleft(), fmt_str=fmt_prefix + fmt_spec
            )

        result_node.values.append(formatted_value)
        result_node.values.append(ast_string_node(blocks.popleft()))

    return result_node


def handle_from_mod_generic_name(node):
    """Convert a `BinOp` `%` formatted str with a unknown name on the `node.right` to an f-string.

    When `node.right` is a Name since we don't know if it's a single var or a dict so we sniff the string.

    `"val: %(key_name1)s val2: %(key_name2)s" % some_dict`
    Sniffs the left string for Dict style usage and calls: `handle_from_mod_dict_name`

    `"val: %s" % some_var`
    Borrow the core logic by injecting the name into a ast.Tuple

    Args:
       node (ast.BinOp): The node to convert to a f-string

    Returns ast.JoinedStr (f-string)
    """

    has_dict_str_format = MOD_KEY_PATTERN.findall(node.left.s)
    if has_dict_str_format:
        return handle_from_mod_dict_name(node)

    # if it's just a name then pretend it's tuple to use that code
    node.right = ast.Tuple(elts=[node.right])
    return handle_from_mod_tuple(node)


def fstringify_node(node):
    fstring_transformer = FstringifyTransformer()
    result = fstring_transformer.visit(node)

    return (
        result,
        dict(
            changed=fstring_transformer.counter > 0,
            lineno=fstring_transformer.lineno,
            col_offset=fstring_transformer.col_offset,
            skip=True,
        ),
    )


def handle_from_mod(node):
    if isinstance(
        node.right, (ast.Name, ast.Attribute, ast.Str, ast.BinOp, ast.Subscript)
    ):
        return handle_from_mod_generic_name(node)

    if isinstance(node.right, ast.Tuple):
        return handle_from_mod_tuple(node)

    if isinstance(node.right, ast.Dict):
        # print("~~~~ Dict mod strings don't make sense to f-strings")
        return node

    raise RuntimeError("unexpected `node.right` class")


class FstringifyTransformer(ast.NodeTransformer):
    def __init__(self):
        super().__init__()
        self.counter = 0
        self.lineno = -1
        self.col_offset = -1

    def visit_call(self, node: ast.Call):
        """Convert `ast.Call` to `ast.JoinedStr` f-string
        """

        match = matching_call(node)

        # bail in these edge cases...
        if match:
            if any(isinstance(arg, ast.Starred) for arg in node.args):
                return node

        if match:
            self.counter += 1
            self.lineno = node.lineno
            self.col_offset = node.col_offset
            result_node = joined_string(node)
            self.visit(result_node)
            return result_node

        return node

    def visit_bin_op(self, node):
        """Convert `ast.BinOp` to `ast.JoinedStr` f-string

        Currently only if a string literal `ast.Str` is on the left side of the `%`
        and one of `ast.Tuple`, `ast.Name`, `ast.Dict` is on the right

        Args:
            node (ast.BinOp): The node to convert to a f-string

        Returns ast.JoinedStr (f-string)
        """

        percent_stringify = (
            isinstance(node.left, ast.Str)
            and isinstance(node.op, ast.Mod)
            and isinstance(
                node.right, (ast.Tuple, ast.Name, ast.Attribute, ast.Str, ast.Subscript)
            )
            # ignore ast.Dict on right
        )

        # bail in these edge cases...
        if percent_stringify:
            for no_good in ["}", "{"]:
                if no_good in node.left.s:
                    return node
            for char in ast.walk(node.right):
                # no nested binops!
                if isinstance(char, ast.BinOp):
                    return node
                # f-string expression part cannot include a backslash
                if isinstance(char, ast.Str) and (
                    any(
                        map(
                            lambda x: x in char.s,
                            ("\n", "\t", "\r", "'", '"', "%s", "%%"),
                        )
                    )
                    or "\\" in char.s
                ):
                    return node

        if percent_stringify:
            self.counter += 1
            self.lineno = node.lineno
            self.col_offset = node.col_offset
            result_node = handle_from_mod(node)
            return result_node

        return node
