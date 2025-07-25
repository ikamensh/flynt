import ast
import io
import re
import tokenize
from typing import Optional, Union

from flynt.exceptions import ConversionRefused
from flynt.linting.fstr_lint import FstrInliner
from flynt.utils.format import QuoteTypes, set_quote_type


def ast_to_string(node: ast.AST) -> str:
    """Convert ``node`` back into source code."""
    txt = ast.unparse(node).rstrip()
    # ``ast.unparse`` wraps ternary expressions in ``FormattedValue`` with
    # redundant parentheses, e.g. ``f"{(a if c else b)}"``.  Remove them to
    # match the style previously produced via ``astor``.
    if isinstance(node, ast.JoinedStr):
        txt = re.sub(r"\{\(([^{}]+?\sif\s[^{}]+?\selse\s[^{}]+?)\)\}", r"{\1}", txt)
    return txt


def is_str_literal(node: ast.AST) -> bool:
    """Return ``True`` if ``node`` is a string literal or an f-string."""
    return isinstance(node, ast.JoinedStr) or is_str_constant(node)


def is_str_constant(node: ast.AST) -> bool:
    """Return ``True`` if ``node`` represents a plain string constant."""
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def get_str_value(node: ast.AST) -> str:
    """Extract the string value from ``node`` which must be a str constant."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    raise TypeError(f"Expected string constant, got {type(node)}")


class StringInStringVisitor(ast.NodeVisitor):
    def __init__(self):
        self.string_in_string = False
        self.in_fmt_value = False

    def _visit_string_node(self) -> None:
        if self.in_fmt_value:
            self.string_in_string = True

    def visit_FormattedValue(self, node):
        if self.in_fmt_value:
            self.generic_visit(node.value)
            return

        self.in_fmt_value = True
        self.generic_visit(node.value)
        self.in_fmt_value = False

    def visit_JoinedStr(self, node):
        if self.in_fmt_value:
            self.string_in_string = True
        self.generic_visit(node)

    def visit_Str(self, node):
        self._visit_string_node()

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            self._visit_string_node()


def str_in_str(node: ast.AST) -> bool:
    sisv = StringInStringVisitor()
    sisv.visit(node)
    return sisv.string_in_string


def ast_formatted_value(
    val: ast.AST,
    fmt_str: Optional[str] = None,
    conversion: Optional[str] = None,
) -> Union[ast.FormattedValue, ast.Constant]:
    if isinstance(val, ast.FormattedValue):
        return val

    if ast_to_string(val).startswith("{"):
        raise ConversionRefused(
            "values starting with '{' are better left not transformed.",
        )

    if (
        fmt_str in (None, "")
        and conversion is None
        and isinstance(val, ast.Call)
        and isinstance(val.func, ast.Name)
        and val.func.id in {"str", "repr"}
        and not val.keywords
        and len(val.args) == 1
    ):
        conversion = f"!{'s' if val.func.id == 'str' else 'r'}"
        val = val.args[0]

    if fmt_str:
        format_spec = ast.JoinedStr([ast_string_node(fmt_str)])
    else:
        format_spec = None

    conversion_val = -1 if conversion is None else ord(conversion.replace("!", ""))

    if format_spec is None and is_str_constant(val):
        return val  # type:ignore[return-value]

    return ast.FormattedValue(
        value=val,
        conversion=conversion_val,
        format_spec=format_spec,
    )


def ast_string_node(string: str) -> ast.Constant:
    return ast.Constant(value=string)


def fixup_transformed(tree: ast.AST, quote_type: Optional[str] = None) -> str:
    """Given a transformed string / fstring ast node, transform it to a string."""
    # check_is_string_node(tree)
    il = FstrInliner()
    il.visit(tree)
    try:
        new_code = ast_to_string(tree)
    except ValueError as exc:
        # ``ast.unparse`` raises ``ValueError`` on invalid conversions prior to
        # Python 3.12.  Treat this as a refused conversion so the caller can
        # gracefully skip the transformation.
        if "Unknown f-string conversion" in str(exc):
            raise ConversionRefused(str(exc)) from exc
        else:
            raise
    if quote_type is None:
        if isinstance(tree, ast.Constant) and isinstance(tree.value, str):
            quote_type = QuoteTypes.double
        elif isinstance(tree, ast.JoinedStr):
            quote_type = QuoteTypes.double
        elif new_code[:4] == 'f"""' or new_code[:3] == "'''" or new_code[:3] == '"""':
            quote_type = QuoteTypes.double
    if quote_type is not None:
        new_code = set_quote_type(new_code, quote_type)
    new_code = new_code.replace("\n", "\\n")
    new_code = new_code.replace("\t", "\\t")
    # ast.parse(new_code)
    return new_code


def contains_comment(code: str) -> bool:
    tokens = tokenize.generate_tokens(io.StringIO(code).readline)
    for token in tokens:
        if token.type == tokenize.COMMENT:
            return True
    return False
