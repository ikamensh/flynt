import io
import token
import tokenize
from collections import deque

from fstringify.utils import get_indent
from fstringify.transform import fstringify_code


def get_chunk(code):
    g = tokenize.tokenize(io.BytesIO(code.encode("utf-8")).readline)
    chunk = []
    END_CHECK = 58  # token.N_TOKENS in 3.7
    for item in g:
        toknum, tokval, start, end, content = item
        if toknum in (token.NEWLINE, token.DEDENT, token.COMMENT):
            if chunk:
                if toknum in (token.NEWLINE, token.DEDENT):
                    chunk.append(item)
                yield chunk
                chunk = []
        else:
            if not chunk and toknum == END_CHECK:  # token.N_TOKENS in 3.7
                continue

            chunk.append(item)


format_call_sequence = [3, 53, 1]
def is_format_call(history: deque):
    toknums = [e[0] for e in history]
    tokvals = [e[1] for e in history]
    return toknums == format_call_sequence and tokvals[-1] == "format"


from typing import Tuple, Generator
code_start = Tuple[int,int]
code_end = Tuple[int,int]
position = Tuple[code_start, code_end]
def get_fstringify_lines(code: str) -> 'Generator[position]':

    for chunk in get_chunk(code):
        print(chunk)
        start = chunk[0][2]  # first line -> 2 idx is start -> is line
        end = chunk[-1][3]  # last line -> 3 idx is end -> is line

        last_toknum = None
        last_tokval = None
        format_perc = False
        format_call = False

        history = deque(maxlen=3)

        for toknum, tokval, _, _, _ in chunk:
            history.append( (toknum, tokval) )
            format_call = format_call or is_format_call(history)
            if (
                toknum == 53
                and tokval == "%"
                and last_toknum == 3
                and "\\n" not in last_tokval
                and "\n" not in last_tokval
                and "%%" not in last_tokval
            ):
                format_perc = True
            # punt if this happens
            elif format_perc and toknum == 53 and tokval == ":":
                format_perc = False  # punt on this (see django_noop7 test)
                break

            if not (toknum in (56, 58) and tokval == "\n"):  # 3.7 is 56...
                last_toknum = toknum
                last_tokval = tokval

        if format_perc or format_call:
            yield (start, end)

#
# def fstringify_code_by_line(code: str):
#     raw_code_lines = code.split("\n")
#     process_range = []
#     scopes_by_idx = {}
#     for positions in get_fstringify_lines(code):
#         # for start, end in positions:
#         if not positions:
#             continue
#         (start, start_pos), (end, end_pos) = positions
#         start_idx = start - 1
#         raw_scope = raw_code_lines[start_idx:end]
#         if not raw_scope:
#             continue
#
#         strip_scope = map(lambda x: x.strip(), raw_scope)
#         scopes_by_idx[start_idx] = dict(
#             raw_scope=raw_scope,
#             strip_scope=strip_scope,
#             indent=get_indent(raw_scope[0]),
#         )
#         process_range += list(range(start_idx, end))
#
#     result_lines = []
#     for line_idx, raw_line in enumerate(raw_code_lines):
#
#         if line_idx not in process_range:
#             result_lines.append(raw_line)
#             continue
#
#         if line_idx not in scopes_by_idx:
#             continue
#
#         scoped = scopes_by_idx[line_idx]
#         code_line, meta = fstringify_code("\n".join(scoped["strip_scope"]))
#
#         if not meta["changed"]:
#             result_lines += scoped["raw_scope"]
#             continue
#
#         code_line = force_double_quote_fstring(code_line)
#         code_line_parts = code_line.strip().split("\n")
#
#         indie = ""
#         indent = scoped["indent"]
#         for idx, cline in enumerate(code_line_parts):
#             code_line_strip = cline.lstrip()  # if change_add else cline
#             if idx == 0:
#                 indie = indent + code_line_strip
#             else:
#                 if (
#                     indie.endswith(",")
#                     or indie.endswith("else")
#                     or indie.endswith("for")
#                     or indie.endswith("in")
#                     or indie.endswith("not")
#                 ):
#                     indie += " "
#
#                 indie += cline.strip()
#                 # else:
#                 #     indie += cline.strip()
#
#         result_lines.append(indie)
#
#     final_code = "\n".join(result_lines)
#     return final_code

def fstringify_code_by_line(code: str):

    current_line = 0
    result_pieces = []

    raw_code_lines = code.split("\n")

    for positions in get_fstringify_lines(code):
        # for start, end in positions:

        (start, start_pos), (end, end_pos) = positions
        start_idx = start - 1
        while current_line < start_idx:
            result_pieces.append(raw_code_lines[current_line]+'\n')
            current_line += 1

        line = raw_code_lines[start_idx]

        to_process, rest = line[:end_pos], line[end_pos:]
        new_line, meta = fstringify_code(to_process)
        if meta['changed']:
            result_pieces +=[new_line, rest+"\n"]
        else:
            result_pieces.append(line+"\n")

        current_line += 1

    while len(raw_code_lines) > current_line:
        result_pieces.append(raw_code_lines[current_line] + '\n')
        current_line += 1

    return "".join(result_pieces)[:-1] #last new line is extra.


def skip_file(filename):
    """use tokenizer to make a fancier
        `"s%" not in contents`
    """
    # fn = io.BytesIO(fn.encode("utf-8")).readline
    with open(filename, "rb") as f:
        try:
            g = tokenize.tokenize(f.readline)
            for toknum, tokval, _, _, _ in g:
                if toknum == 53 and tokval == "%":
                    return False
        except tokenize.TokenError:
            pass

        return True
