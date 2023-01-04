import ast
import token
from collections import deque
from typing import Deque, Iterable, Iterator, Optional

from flynt.lexer.context import LexerContext
from flynt.lexer.PyToken import PyToken

REUSE = "Token was not used"


class Chunk:
    def __init__(
        self,
        tokens: Iterable[PyToken] = (),
        *,
        lexer_context: LexerContext,
    ) -> None:
        self.lexer_context = lexer_context

        self.tokens: Deque[PyToken] = deque(tokens)
        self.complete = False

        self.is_percent_chunk = False
        self.percent_ongoing = False

        self.is_call_chunk = False
        self.successful = False

        self.string_in_string = False

    def empty_append(self, t: PyToken) -> None:
        if not t.is_string() or t.is_raw_string():
            self.complete = True

        self.tokens.append(t)

    def second_append(self, t: PyToken) -> None:
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

    def percent_append(self, t: PyToken) -> Optional[str]:
        # todo handle all cases?
        if not self[0].is_string():
            self.complete = True
            return None

        if len(self) == 2:
            self.tokens.append(t)
            if self.is_parseable:
                self.successful = True
            else:
                self.percent_ongoing = True

        else:
            if self.percent_ongoing:
                self.tokens.append(t)
                if t.is_string() and "{" not in str(self):
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
        return None

    def call_append(self, t: PyToken) -> None:
        if t.is_string():
            self.string_in_string = True

        if len(self) == 2 and t.tokval != "format":
            self.complete = True
            self.successful = False
            return

        self.tokens.append(t)
        if len(self) > 3 and self.is_parseable:
            self.complete = True
            self.successful = True

    def append(self, t: PyToken) -> Optional[str]:
        # stop on a comment or too long chunk
        if t.toknum in self.lexer_context.break_tokens:
            self.complete = True
            self.successful = self.is_parseable and (
                self.is_percent_chunk or self.is_call_chunk
            )
            return None

        if len(self) > 50:
            self.complete = True
            self.successful = False
            return None

        if t.toknum in self.lexer_context.skip_tokens:
            return None

        if len(self) == 0:
            self.empty_append(t)
        elif not (self.is_call_chunk or self.is_percent_chunk):
            self.second_append(t)
        elif self.is_call_chunk:
            self.call_append(t)
        else:
            return self.percent_append(t)
        return None

    @property
    def is_parseable(self) -> bool:
        if len(self.tokens) < 1:
            return False
        try:
            ast.parse(str(self))
            return True
        except SyntaxError:
            return False

    @property
    def start_line(self) -> int:
        return self.tokens[0].start[0] - 1

    @property
    def start_idx(self) -> int:
        return self.tokens[0].start[1]

    @property
    def end_idx(self) -> int:
        return self.tokens[-1].end[1]

    @property
    def end_line(self) -> int:
        return self.tokens[-1].end[0] - 1

    @property
    def n_lines(self) -> int:
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
    def quote_type(self) -> Optional[str]:
        return self.tokens[0].get_quote_type()

    def __getitem__(self, item: int) -> PyToken:
        return self.tokens[item]

    def __iter__(self) -> Iterator[PyToken]:
        return iter(self.tokens)

    def __len__(self) -> int:
        return len(self.tokens)

    def __str__(self) -> str:
        return " ".join(t.tokval for t in self)

    def __repr__(self):
        if self.tokens:
            return f"Chunk: {self}"
        return "Empty Chunk"
