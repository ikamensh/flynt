import io
import ast
import token
from collections import deque
import tokenize
from typing import Generator, Tuple, List, Deque
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
        self.line: str = line

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

class Chunk:
    def __init__(self, tokens = ()):
        self.tokens: Deque[PyToken] = deque(tokens)
        self.complete = False

    def append(self, t: PyToken):
        if t.toknum in (token.NEWLINE, token.NL, token.COMMENT):
            self.complete = True

        if t.toknum not in (token.COMMENT, token.ENCODING):
            self.tokens.append(t)

    def discard_beginning(self):
        while self.tokens[0].toknum != token.STRING:
            self.tokens.popleft()

    @property
    def is_parseable(self):
        if len(self.tokens) < 1:
            return False
        try:
            ast.parse(self.tokens[0].line[self.start_idx:self.end_idx])
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

    @property
    def end_implicit_string_concat(self):
        if len(self) < 2:
            return False
        else:
            return self.tokens[-2].toknum == token.STRING and \
                   self.tokens[-1].toknum in (token.NL, token.NEWLINE)

    @property
    def start_implicit_string_concat(self):
        if len(self) < 1:
            return False
        else:
            return self.tokens[0].toknum == token.STRING

    @property
    def is_multiline(self):
        if len(self) < 2:
            return False
        else:
            return self.tokens[0].start[0] != self.tokens[-1].end[0]

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

    def __repr__(self):
        if self.tokens:
            return "Chunk: "+self.tokens[0].line[:self.end_idx]
        else:
            return "Empty Chunk"



def get_chunks(code) -> Generator[Chunk, None, None]:
    g = tokenize.tokenize(io.BytesIO(code.encode("utf-8")).readline)
    chunk = Chunk()
    for item in g:
        t = PyToken(item)
        chunk.append(t)
        if chunk.complete:
            yield chunk
            chunk = Chunk()

format_call_sequence = [token.STRING, token.OP, token.NAME]
def is_format_call(history: Deque[PyToken]):
    toknums = [e.toknum for e in history]
    return toknums == format_call_sequence and \
           history[-2].tokval == "." and \
           history[-1].tokval == "format"

def is_percent_formating(history: Deque[PyToken]):
    return len(history) == 3 and history[0].is_percent_string() and history[1].is_percent_op()

def get_fstringify_lines(code: str) -> Generator[Chunk, None, None]:
    """
    A generator yielding tuples of line number, starting and ending character
    corresponding to the parts of the code where fstring can be formed.
    """

    prev_implicit_string_concat = False
    for chunk in get_chunks(code):

        if not chunk or chunk.is_multiline or chunk.contains_raw_strings:
            continue

        if prev_implicit_string_concat and chunk.start_implicit_string_concat:
            prev_implicit_string_concat = chunk.end_implicit_string_concat
            continue

        history: Deque[PyToken] = deque(maxlen=3)

        for i, t in enumerate(chunk):
            history.append(t)

            if is_format_call(history) or is_percent_formating(history):
                c = smallest_chunk(chunk, history, i)

                if c and not c.contains_multiple_string_tokens:
                    yield c
                break

        prev_implicit_string_concat = chunk.end_implicit_string_concat


def smallest_chunk(chunk, history, i):
    c = Chunk(history)
    if is_format_call(history):
        i += 1
        c.append(chunk[i])
    try:
        while not c.is_parseable:
            i += 1
            c.append(chunk[i])
    except IndexError:
        return None
    if is_percent_formating(history):
        try:
            while chunk[i + 1].is_expr_continuation_op():
                i += 1
                c.append(chunk[i])
                while not c.is_parseable:
                    i += 1
                    c.append(chunk[i])
        except IndexError:
            pass
    return c

