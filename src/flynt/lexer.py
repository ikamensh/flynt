import io
import ast
import token
from collections import deque
import tokenize
from typing import Generator, Tuple, Deque
from flynt.format import QuoteTypes


line_num = int
char_idx = int
class PyToken:
    percent_cant_handle = ("%%",)

    def __init__(self, t):
        toknum, tokval, start, end, line = t
        self.toknum: int = toknum
        self.tokval: str = tokval
        self.start: Tuple[line_num, char_idx] = start
        self.end: Tuple[line_num, char_idx] = end

    def is_percent_op(self):
        return self.toknum == token.OP and self.tokval == "%"

    def is_expr_continuation_op(self):
        return self.is_sq_brack_op() or \
               self.is_paren_op() or \
               self.is_dot_op() or \
               self.is_exponentiation_op()

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
        return self.toknum == token.STRING and \
               not any(s in self.tokval for s in PyToken.percent_cant_handle)

    def get_quote_type(self):
        assert self.toknum is token.STRING
        for qt in QuoteTypes.all:
            if self.tokval[:len(qt)] == qt and self.tokval[-len(qt):] == qt:
                return qt

        if self.is_legacy_unicode_string():
            for qt in QuoteTypes.all:
                if self.tokval[1:len(qt)+1] == qt and self.tokval[-len(qt):] == qt:
                    return qt

        raise Exception(f"Can't determine quote type of the string {self.tokval}.")

    def is_legacy_unicode_string(self):
        return self.toknum == token.STRING and self.tokval[0] == 'u'

    def is_raw_string(self):
        return self.toknum == token.STRING and self.tokval[0] == 'r'

    def __repr__(self):
        return f"PyToken {self.toknum} : {self.tokval}"

REUSE = "Token was not used"

class Chunk:

    skip_tokens = ()
    break_tokens = ()

    @staticmethod
    def set_multiline():
        Chunk.skip_tokens = (token.NEWLINE, token.NL)
        Chunk.break_tokens = (token.COMMENT,)

    @staticmethod
    def set_single_line():
        Chunk.skip_tokens = ()
        Chunk.break_tokens = (token.COMMENT, token.NEWLINE, token.NL)


    def __init__(self, tokens = ()):
        self.tokens: Deque[PyToken] = deque(tokens)
        self.complete = False

        self.is_percent_chunk = False
        self.percent_ongoing = False

        self.is_call_chunk = False
        self.successful = False

    def empty_append(self, t: PyToken):
        if t.is_string() and not t.is_raw_string():
            self.tokens.append(t)

    def second_append(self, t: PyToken):
        if t.is_string():
            self.tokens[0].tokval += t.tokval
            self.tokens[0].end = t.end
        elif t.is_percent_op():
            self.tokens.append(t)
            self.is_percent_chunk = True
        elif t.is_dot_op():
            self.tokens.append(t)
            self.is_call_chunk = True
        else:
            self.complete = True

    def percent_append(self, t: PyToken):

        # No string in string
        if t.is_string():
            self.complete = True
            self.successful = self.is_parseable
            return REUSE

        #todo handle all cases?
        if not self[0].is_percent_string():
            self.complete = True
            return

        if len(self) == 2:
            self.tokens.append(t)
            if self.is_parseable:
                self.successful = True
            else:
                self.percent_ongoing = True

        else:
            if self.percent_ongoing:
                self.tokens.append(t)
                if self.is_parseable:
                    self.percent_ongoing = False
                    self.successful = True
            elif t.is_expr_continuation_op():
                self.tokens.append(t)
                self.percent_ongoing = True
            else:
                self.complete = True
                self.successful = self.is_parseable
                return REUSE

    def call_append(self, t: PyToken):

        # no string in string
        if t.is_string():
            self.complete = True
            self.successful = False
            return

        self.tokens.append(t)
        if len(self) > 3 and self.is_parseable:
            self.complete = True
            self.successful = True

    def append(self, t: PyToken):
        # stop on a comment or too long chunk
        if t.toknum in self.break_tokens:
            self.complete = True
            self.successful = self.is_parseable and \
                              (self.is_percent_chunk or self.is_call_chunk)
            return

        if len(self) > 50:
            self.complete = True
            self.successful = False
            return

        if t.toknum in self.skip_tokens:
            return

        if len(self) == 0:
            self.empty_append(t)
        elif not (self.is_call_chunk or self.is_percent_chunk):
            self.second_append(t)
        elif self.is_call_chunk:
            self.call_append(t)
        elif self.is_percent_chunk:
            return self.percent_append(t)


    @property
    def is_parseable(self):
        if len(self.tokens) < 1:
            return False
        try:
            ast.parse(str(self))
            return True
        except SyntaxError:
            return False

    @property
    def line(self):
        return self.tokens[0].start[0] - 1

    @property
    def start_idx(self):
        return self.tokens[0].start[1]

    @property
    def end_idx(self):
        return self.tokens[-1].end[1]


    #todo test multiline for comment between implicit concat
    @property
    def end_implicit_string_concat(self):
        if len(self) < 2:
            return False
        else:
            return self.tokens[-2].toknum == token.STRING and \
                   self.tokens[-1].toknum in (token.NL, token.NEWLINE)

    @property
    def n_lines(self):
        return 1 + self.tokens[-1].end[0] - self.tokens[0].start[0]

    @property
    def start_implicit_string_concat(self):
        if len(self) < 1:
            return False
        else:
            return self.tokens[0].toknum == token.STRING

    @property
    def is_multiline(self):
        return self.n_lines > 1

    @property
    def contains_raw_strings(self):
        return any(tok.is_raw_string() for tok in self.tokens)

    @property
    def contains_multiple_string_tokens(self):
        return sum(t.toknum == token.STRING for t in self.tokens) > 1

    def __getitem__(self, item):
        return self.tokens[item]

    def __iter__(self):
        return iter(self.tokens)

    def __len__(self):
        return len(self.tokens)

    def __str__(self):
        return " ".join(t.tokval for t in self)

    def __repr__(self):
        if self.tokens:
            return "Chunk: " + str(self)
        else:
            return "Empty Chunk"

set_multiline = Chunk.set_multiline
set_single_line = Chunk.set_single_line
# multiline mode is the default
set_multiline()

def get_chunks(code) -> Generator[Chunk, None, None]:
    g = tokenize.tokenize(io.BytesIO(code.encode("utf-8")).readline)
    chunk = Chunk()
    for item in g:
        t = PyToken(item)
        reuse = chunk.append(t)
        if chunk.complete:
            yield chunk
            chunk = Chunk()
            if reuse:
                chunk.append(t)

    yield chunk


def get_fstringify_chunks(code: str) -> Generator[Chunk, None, None]:
    """
    A generator yielding Chunks of the code where fstring can be formed.
    """
    for chunk in get_chunks(code):
        if chunk.successful:
            yield chunk



