import ast
import sys
import token
from collections import deque
from typing import Deque

from flynt.lexer.py_token import PyToken

REUSE = "Token was not used"


if sys.version_info.major == 3 and sys.version_info.minor == 6:
    MULTILINE_SKIP = (token.NEWLINE, 58)
    MULTILINE_BREAK = (57,)

    SINGLE_SKIP = ()
    SINGLE_BREAK = (token.NEWLINE, 57, 58)
else:
    MULTILINE_SKIP = (token.NEWLINE, token.NL)
    MULTILINE_BREAK = (token.COMMENT,)

    SINGLE_SKIP = ()
    SINGLE_BREAK = (token.COMMENT, token.NEWLINE, token.NL)


class Chunk:

    skip_tokens = ()
    break_tokens = ()
    multiline = None

    @classmethod
    def set_multiline(cls):
        cls.skip_tokens = MULTILINE_SKIP
        cls.break_tokens = MULTILINE_BREAK
        cls.multiline = True

    @classmethod
    def set_single_line(cls):
        cls.skip_tokens = SINGLE_SKIP
        cls.break_tokens = SINGLE_BREAK
        cls.multiline = False

    def __init__(self, tokens=()):
        self.tokens: Deque[PyToken] = deque(tokens)
        self.complete = False

        self.is_percent_chunk = False
        self.percent_ongoing = False

        self.is_call_chunk = False
        self.successful = False

        self.string_in_string = False

    def empty_append(self, py_token: PyToken):
        if py_token.is_string() and not py_token.is_raw_string():
            pass
        else:
            self.complete = True

        self.tokens.append(py_token)

    def second_append(self, py_token: PyToken):
        if py_token.is_string():
            self.tokens[0].tokval += py_token.tokval
            self.tokens[0].end = py_token.end
        elif py_token.is_percent_op():
            self.tokens.append(py_token)
            self.is_percent_chunk = True
        elif py_token.is_dot_op():
            self.tokens.append(py_token)
            self.is_call_chunk = True
        else:
            self.tokens.append(py_token)
            self.complete = True

    def percent_append(self, py_token: PyToken):

        # No string in string
        if py_token.is_string():
            self.complete = True
            self.successful = self.is_parseable
            return REUSE

        # todo handle all cases?
        if not self[0].is_percent_string():
            self.complete = True
            return

        if len(self) == 2:
            self.tokens.append(py_token)
            if self.is_parseable:
                self.successful = True
            else:
                self.percent_ongoing = True

        else:
            if self.percent_ongoing:
                self.tokens.append(py_token)
                if self.is_parseable:
                    self.percent_ongoing = False
                    self.successful = True
            elif py_token.is_expr_continuation_op():
                self.tokens.append(py_token)
                self.percent_ongoing = True
            else:
                self.complete = True
                self.successful = self.is_parseable
                return REUSE

    def call_append(self, py_token: PyToken):

        if py_token.is_string():
            self.string_in_string = True

        self.tokens.append(py_token)
        if len(self) > 3 and self.is_parseable:
            self.complete = True
            self.successful = True

    def append(self, py_token: PyToken):
        # stop on a comment or too long chunk
        if py_token.toknum in self.break_tokens:
            self.complete = True
            self.successful = self.is_parseable and (
                self.is_percent_chunk or self.is_call_chunk
            )
            return

        if len(self) > 50:
            self.complete = True
            self.successful = False
            return

        if py_token.toknum in self.skip_tokens:
            return

        if not self:
            self.empty_append(py_token)
        elif not (self.is_call_chunk or self.is_percent_chunk):
            self.second_append(py_token)
        elif self.is_call_chunk:
            self.call_append(py_token)
        elif self.is_percent_chunk:
            return self.percent_append(py_token)

    @property
    def is_parseable(self):
        try:
            ast.parse(str(self))
            return bool(self.tokens)
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
        return "Empty Chunk"
