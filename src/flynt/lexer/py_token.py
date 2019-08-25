import token
from typing import Tuple

from flynt.format import QuoteTypes
from flynt.exceptions import FlyntException

LINE_NUM = int()
CHAR_IDX = int()


class PyToken:
    percent_cant_handle = ("%%",)

    def __init__(self, t):
        toknum, tokval, start, end, _ = t
        self.toknum: int = toknum
        self.tokval: str = tokval
        self.start: Tuple[LINE_NUM, CHAR_IDX] = start
        self.end: Tuple[LINE_NUM, CHAR_IDX] = end

    def is_percent_op(self):
        return self.toknum == token.OP and self.tokval == "%"

    def is_expr_continuation_op(self):
        return (
            self.is_sq_brack_op()
            or self.is_paren_op()
            or self.is_dot_op()
            or self.is_exponentiation_op()
        )

    def is_sq_brack_op(self):
        return self.toknum == token.OP and self.tokval == "["

    def is_dot_op(self):
        return self.toknum == token.OP and self.tokval == "."

    def is_paren_op(self):
        return self.toknum == token.OP and self.tokval == "("

    def is_exponentiation_op(self):
        return self.toknum == token.OP and self.tokval == "**"

    def is_string(self):
        return self.toknum == token.STRING

    def is_percent_string(self):
        return self.toknum == token.STRING and not any(
            s in self.tokval for s in PyToken.percent_cant_handle
        )

    def get_quote_type(self):
        assert self.toknum is token.STRING
        for quote_type in QuoteTypes.all:
            if (
                self.tokval[: len(quote_type)] == quote_type
                and self.tokval[-len(quote_type) :] == quote_type
            ):
                return quote_type

        if self.is_legacy_unicode_string():
            for quote_type in QuoteTypes.all:
                if (
                    self.tokval[1 : len(quote_type) + 1] == quote_type
                    and self.tokval[-len(quote_type) :] == quote_type
                ):
                    return quote_type

        raise FlyntException(f"Can't determine quote type of the string {self.tokval}.")

    def is_legacy_unicode_string(self):
        return self.toknum == token.STRING and self.tokval[0] == "u"

    def is_raw_string(self):
        return self.toknum == token.STRING and self.tokval[0] == "r"

    def __repr__(self):
        return f"PyToken {self.toknum} : {self.tokval}"
