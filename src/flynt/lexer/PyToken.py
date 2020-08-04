import token
from typing import Tuple

from flynt.exceptions import FlyntException
from flynt.format import QuoteTypes

line_num = int
char_idx = int


class PyToken:
    def __init__(self, t):
        toknum, tokval, start, end, line = t
        self.toknum: int = toknum
        self.tokval: str = tokval
        self.start: Tuple[line_num, char_idx] = start
        self.end: Tuple[line_num, char_idx] = end

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

    def get_quote_type(self):
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

    def is_legacy_unicode_string(self):
        return self.toknum == token.STRING and self.tokval[0] == "u"

    def is_raw_string(self):
        return self.toknum == token.STRING and self.tokval[0] == "r"

    def __repr__(self):
        return f"PyToken {self.toknum} : {self.tokval}"
