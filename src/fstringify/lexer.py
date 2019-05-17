import io
import token
from collections import deque
import tokenize
from typing import Generator, Tuple, List, Deque

line_num = int
char_idx = int
class PyToken:
    percent_cant_handle = ("\\n", "\n", "%%")

    def __init__(self, t):
        toknum, tokval, start, end, line = t
        self.toknum: int = toknum
        self.tokval: str = tokval
        self.start: Tuple[line_num, char_idx] = start
        self.end: Tuple[line_num, char_idx] = end
        self.line: str = line

    def is_percent_op(self):
        return self.toknum == token.OP and self.tokval == "%"

    def is_percent_string(self):
        return self.toknum == token.STRING and \
               not any(s in self.tokval for s in PyToken.percent_cant_handle)

    def __repr__(self):
        return f"PyToken {self.toknum} : {self.tokval}"

class Chunk:
    def __init__(self):
        self.tokens: List[PyToken] = []
        self.complete = False

    def append(self, t: PyToken):
        if t.toknum in (token.NEWLINE, token.NL, token.COMMENT):
            self.complete = True

        if t.toknum not in (token.COMMENT, token.ENCODING):
            self.tokens.append(t)

    @property
    def line(self):
        return self.tokens[0].start[0] - 1

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

def get_fstringify_lines(code: str) -> Generator[Tuple[line_num, char_idx], None, None]:
    """
    A generator yielding tuples of line number and ending character
    corresponding to the parts of the code where fstring can be formed.
    """

    prev_implicit_string_concat = False
    for chunk in get_chunks(code):
        if not chunk or chunk.is_multiline:
            continue

        format_perc = False
        format_call = False

        history: Deque[PyToken] = deque(maxlen=3)

        for t in chunk:
            history.append(t)
            if len(history) > 1:
                prev_t = history[-2]
            else:
                continue

            format_call = format_call or is_format_call(history)
            if t.is_percent_op() and prev_t.is_percent_string():
                format_perc = True


        if (format_perc or format_call) and not (prev_implicit_string_concat and chunk.start_implicit_string_concat):
            yield chunk.line, chunk.end_idx

        prev_implicit_string_concat = chunk.end_implicit_string_concat

