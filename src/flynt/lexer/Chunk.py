import ast
import sys
import token
from collections import deque
from typing import Deque

from flynt.lexer.PyToken import PyToken

REUSE = "Token was not used"


is_36 = sys.version_info.major == 3 and sys.version_info.minor == 6
if is_36:
    multiline_skip = (token.NEWLINE, 58)
    multiline_break = (57,)

    single_skip = ()
    single_break = (token.NEWLINE, 57, 58)
else:
    multiline_skip = (token.NEWLINE, token.NL)
    multiline_break = (token.COMMENT,)

    single_skip = ()
    single_break = (token.COMMENT, token.NEWLINE, token.NL)


class Chunk:

    skip_tokens = ()
    break_tokens = ()
    multiline = None

    @staticmethod
    def set_multiline():
        Chunk.skip_tokens = multiline_skip
        Chunk.break_tokens = multiline_break
        Chunk.multiline = True

    @staticmethod
    def set_single_line():
        Chunk.skip_tokens = single_skip
        Chunk.break_tokens = single_break
        Chunk.multiline = False

    def __init__(self, tokens=()):
        self.tokens: Deque[PyToken] = deque(tokens)
        self.complete = False

        self.is_percent_chunk = False
        self.percent_ongoing = False

        self.is_call_chunk = False
        self.successful = False

        self.string_in_string = False

    def empty_append(self, t: PyToken):
        if t.is_string() and not t.is_raw_string():
            pass
        else:
            self.complete = True

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
            self.tokens.append(t)
            self.complete = True

    def percent_append(self, t: PyToken):

        # todo handle all cases?
        if not self[0].is_string():
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
                if t.is_string() and not '{' in str(self):
                    self.string_in_string = True
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

        if t.is_string():
            self.string_in_string = True

        self.tokens.append(t)
        if len(self) > 3 and self.is_parseable:
            self.complete = True
            self.successful = True

    def append(self, t: PyToken):
        # stop on a comment or too long chunk
        if t.toknum in self.break_tokens:
            self.complete = True
            self.successful = self.is_parseable and (
                self.is_percent_chunk or self.is_call_chunk
            )
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
    def start_line(self):
        return self.tokens[0].start[0] - 1

    @property
    def start_idx(self):
        return self.tokens[0].start[1]

    @property
    def end_idx(self):
        return self.tokens[-1].end[1]

    @property
    def end_line(self):
        return self.tokens[-1].end[0] - 1

    @property
    def n_lines(self):
        return 1 + self.end_line - self.start_line

    @property
    def is_multiline(self):
        return self.n_lines > 1

    @property
    def contains_raw_strings(self):
        return any(tok.is_raw_string() for tok in self.tokens)

    @property
    def contains_multiple_string_tokens(self):
        return sum(t.toknum == token.STRING for t in self.tokens) > 1

    @property
    def quote_type(self):
        return self.tokens[0].get_quote_type()

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
