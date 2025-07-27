import ast
import codecs
import io
import re
import tokenize
from typing import Dict, List, Optional, Union

from flynt.exceptions import ConversionRefused
from flynt.linting.fstr_lint import FstrInliner
from flynt.utils.format import QuoteTypes, get_quote_type, set_quote_type


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


unicode_escape_re = re.compile(
    r"\\(?:u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|x[0-9a-fA-F]{2}|N\{[^}]+\})"
)


def unicode_escape_map(literal: str) -> Dict[str, List[str]]:
    """Return mapping of characters to all unicode escape sequences used for them.

    Multiple occurrences of the same character may appear both escaped and
    unescaped in the literal.  This function preserves the order of escapes so
    that they can later be re-applied only to the characters that were escaped
    originally.
    """
    quote = get_quote_type(literal)
    if quote is None:
        return {}
    idx = 0
    while idx < len(literal) and literal[idx] in "furbFURB":
        idx += 1
    body = literal[idx + len(quote) : -len(quote)]
    mapping: Dict[str, List[str]] = {}
    for m in unicode_escape_re.finditer(body):
        esc = m.group(0)
        try:
            char = codecs.decode(esc, "unicode_escape")
        except Exception:  # noqa: S112
            continue
        mapping.setdefault(char, []).append(esc)
    return mapping


def apply_unicode_escape_map(code: str, mapping: Dict[str, List[str]]) -> str:
    """Replace characters in ``code`` with their original escape sequences."""
    if not mapping:
        return code
    pattern = "[" + "".join(re.escape(c) for c in mapping) + "]"

    def repl(match: re.Match[str]) -> str:
        char = match.group(0)
        escapes = mapping.get(char)
        if escapes:
            return escapes.pop(0)
        return char

    return re.sub(pattern, repl, code)


def contains_unicode_escape(code: str) -> bool:
    """Return ``True`` if ``code`` contains unicode escape sequences."""
    return bool(unicode_escape_re.search(code))
