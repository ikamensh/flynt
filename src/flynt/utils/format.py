"""This module deals with quote types for strings.

It includes checking the quote type and changing it."""

import io
import re
import token
import tokenize
from tokenize import TokenInfo
from typing import Optional, Tuple

from flynt.exceptions import FlyntException

lonely_quote = re.compile(r"(?<!\\)\"")
lonely_single_quote = re.compile(r"(?<!\\)\'")


class QuoteTypes:
    single = "'"
    double = '"'
    triple_single = "'''"
    triple_double = '"""'
    all = [triple_double, triple_single, single, double]


def get_string_prefix(code: str) -> str:
    """Return the leading string prefix characters (r, u, b, f)."""
    idx = 0
    while idx < len(code) and code[idx] in "furbFURB":
        idx += 1
    return code[:idx]


line_num = int
char_idx = int


class PyToken:
    def __init__(self, t: TokenInfo) -> None:
        toknum, tokval, start, end, line = t
        self.toknum: int = toknum
        self.tokval: str = tokval
        self.start: Tuple[line_num, char_idx] = start
        self.end: Tuple[line_num, char_idx] = end

    def get_quote_type(self) -> Optional[str]:
        if self.toknum is not token.STRING:
            return None

        tokval = self.tokval
        idx = 0
        while idx < len(tokval) and tokval[idx] in "furbFURB":
            idx += 1

        for qt in QuoteTypes.all:
            if tokval[idx : idx + len(qt)] == qt and tokval[-len(qt) :] == qt:
                return qt

        raise FlyntException(f"Can't determine quote type of the string {self.tokval}.")

    def __repr__(self):
        return f"PyToken {self.toknum} : {self.tokval}"


def get_quote_type(code: str) -> Optional[str]:
    g = tokenize.tokenize(io.BytesIO(code.encode("utf-8")).readline)
    next(g)
    t = PyToken(next(g))

    return t.get_quote_type()


def remove_quotes(code: str) -> str:
    prefix = get_string_prefix(code)
    quote_type = get_quote_type(code)
    if quote_type:
        return code[len(prefix) + len(quote_type) : -len(quote_type)]
    return code[len(prefix) :]


def set_quote_type(code: str, quote_type: str) -> str:
    prefix = get_string_prefix(code)
    has_f = "f" in prefix.lower()
    other_prefix = "".join(ch for ch in prefix if ch.lower() != "f")
    body = remove_quotes(code)
    if quote_type in (QuoteTypes.single, QuoteTypes.triple_double):
        if body[-2:] == '\\"':
            body = f'{body[:-2]}"'
    elif quote_type is QuoteTypes.double:
        body = lonely_quote.sub('\\"', body)

    if quote_type == QuoteTypes.single:
        body = lonely_single_quote.sub("\\'", body)

    return other_prefix + ("f" if has_f else "") + quote_type + body + quote_type
