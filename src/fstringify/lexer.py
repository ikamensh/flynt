import io
import token
from collections import deque
import tokenize
from typing import Generator, Tuple, List

line_num = int
char_idx = int
class PyToken:
    def __init__(self, t):
        toknum, tokval, start, end, line = t
        self.toknum: int = toknum
        self.tokval: str = tokval
        self.start: Tuple[line_num, char_idx] = start
        self.end: Tuple[line_num, char_idx] = end
        self.line: str = line

class Chunk:
    def __init__(self):
        self.tokens: List[PyToken] = []
        self.complete = False

    def append(self, t: PyToken):
        if t.toknum in (token.NEWLINE, token.DEDENT, token.COMMENT):
            self.complete = True

        if t.toknum is not token.COMMENT:
            self.tokens.append(t)

    @property
    def line(self):
        return self.tokens[0].start[0]

    @property
    def end_idx(self):
        return self.tokens[-1].end[1]

    def __iter__(self):
        return iter(self.tokens)



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
def is_format_call(history: deque):
    toknums = [e[0] for e in history]
    tokvals = [e[1] for e in history]
    return toknums == format_call_sequence and tokvals[-1] == "format"

def get_fstringify_lines(code: str) -> Generator[Tuple[line_num, char_idx], None, None]:
    """
    A generator yielding tuples of line number and ending character
    corresponding to the parts of the code where fstring can be formed.
    """

    for chunk in get_chunks(code):
        print(chunk)
        line = chunk.line
        end_idx = chunk.end_idx

        last_toknum = None
        last_tokval = None
        format_perc = False
        format_call = False

        history = deque(maxlen=3)

        for t in chunk:
            history.append( (t.toknum, t.tokval) )
            format_call = format_call or is_format_call(history)
            if (
                t.toknum == token.OP
                and t.tokval == "%"
                and last_toknum == token.STRING
                and "\\n" not in last_tokval
                and "\n" not in last_tokval
                and "%%" not in last_tokval
            ):
                format_perc = True

            # punt if this happens
            elif format_perc and t.toknum == token.OP and t.tokval == ":":
                format_perc = False  # punt on this (see django_noop7 test)
                break

            if not (t.toknum in (token.NL, token.N_TOKENS) and t.tokval == "\n"):
                last_toknum = t.toknum
                last_tokval = t.tokval

        if format_perc or format_call:
            yield line, end_idx