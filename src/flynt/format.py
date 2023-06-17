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

        for qt in QuoteTypes.all:
            if self.tokval[: len(qt)] == qt and self.tokval[-len(qt) :] == qt:
                return qt

        if self.is_legacy_unicode_string():
            for qt in QuoteTypes.all:
                if self.tokval[1 : len(qt) + 1] == qt and self.tokval[-len(qt) :] == qt:
                    return qt

        raise FlyntException(f"Can't determine quote type of the string {self.tokval}.")

    def is_legacy_unicode_string(self) -> bool:
        return self.toknum == token.STRING and self.tokval[0] == "u"

    def __repr__(self):
        return f"PyToken {self.toknum} : {self.tokval}"


def get_quote_type(code: str) -> Optional[str]:

    g = tokenize.tokenize(io.BytesIO(code.encode("utf-8")).readline)
    next(g)
    t = PyToken(next(g))

    return t.get_quote_type()


def remove_quotes(code: str) -> str:
    quote_type = get_quote_type(code)
    if quote_type:
        return code[len(quote_type) : -len(quote_type)]
    return code


def set_quote_type(code: str, quote_type: str) -> str:
    if code[0] == "f":
        prefix, body = "f", remove_quotes(code[1:])
    else:
        prefix, body = "", remove_quotes(code)
    if quote_type in (QuoteTypes.single, QuoteTypes.triple_double):
        if body[-2:] == '\\"':
            body = f'{body[:-2]}"'
    elif quote_type is QuoteTypes.double:
        body = lonely_quote.sub('\\"', body)

    if quote_type == QuoteTypes.single:
        body = lonely_single_quote.sub("\\'", body)

    return prefix + quote_type + body + quote_type
