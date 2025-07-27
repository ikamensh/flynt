"""Utilities for working with string quote types."""

import re
from typing import Optional

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


def get_quote_type(code: str) -> Optional[str]:
    """Return the quote token used for ``code``."""
    match = re.match(r"[furbFURB]*(['\"]{3}|['\"])", code)
    if match:
        return match.group(1)
    raise FlyntException(f"Can't determine quote type of the string {code}.")


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
