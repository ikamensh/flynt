import io
import token
import tokenize

from fstringify.utils import get_indent, get_lines
from fstringify.transform import fstringify_code
from fstringify.format import force_double_quote_fstring


def skip_line(raw_line):
    punt = False
    try:
        g = tokenize.tokenize(io.BytesIO(raw_line.encode("utf-8")).readline)
        found_bin_op = False
        found_paren = False
        for toknum, tokval, _, _, _ in g:
            # print(toknum, tokval)
            if toknum == 53 and tokval == "%":
                found_bin_op = True
            elif found_bin_op and toknum == 53 and tokval == "(":
                found_paren = True
            elif found_bin_op and not found_paren and toknum == 1 and tokval == "if":
                punt = True
            elif found_bin_op and toknum == 53 and tokval == ":":
                punt = False
    except tokenize.TokenError:
        pass

    return punt


def usable_chunk(fn):
    """use tokenizer to make a fancier
        `"s%" not in contents`
    """
    f = io.BytesIO(fn.encode("utf-8"))

    try:
        g = tokenize.tokenize(f.readline)
        last_toknum = None
        last_tokval = None
        for toknum, tokval, _, _, _ in g:
            if (
                toknum == 53
                and tokval == "%"
                and last_toknum == 3
                and "\\n" not in last_tokval
            ):
                return True

            last_toknum = toknum
            last_tokval = tokval
    except tokenize.TokenError:
        pass

    return False


def get_chunk(code):
    g = tokenize.tokenize(io.BytesIO(code.encode("utf-8")).readline)
    chunk = []
    END_CHECK = 58  # token.N_TOKENS in 3.7
    for item in g:
        toknum, tokval, start, end, content = item
        if toknum in (token.NEWLINE, token.DEDENT):
            if chunk:
                chunk.append(item)
                yield chunk
                chunk = []
        else:
            if not chunk and toknum == END_CHECK:  # token.N_TOKENS in 3.7
                continue

            chunk.append(item)


def get_str_bin_op_lines(code):
    from collections import deque
    format_call_sequence = deque([3, 53, 1])

    for chunk in get_chunk(code):
        start = chunk[0][2][0]  # first line -> 2 idx is start -> is line
        end = chunk[-1][3][0]  # last line -> 3 idx is end -> is line

        last_toknum = None
        last_tokval = None
        format_perc = False
        format_call = False
        dq = deque(maxlen=3)

        for toknum, tokval, _, _, _ in chunk:
            dq.append(toknum)
            if dq == format_call_sequence:
                if tokval == "format":
                    format_call = True
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


def fstringify_code_by_line(code: str, debug=False):
    raw_code_lines = code.split("\n")
    no_skip_range = []
    scopes_by_idx = {}
    for positions in get_str_bin_op_lines(code):
        # for start, end in positions:
        if not positions:
            continue
        start, end = positions
        start_idx = start - 1
        raw_scope = raw_code_lines[start_idx:end]
        if not raw_scope:
            continue

        strip_scope = map(lambda x: x.strip(), raw_scope)
        scopes_by_idx[start_idx] = dict(
            raw_scope=raw_scope,
            strip_scope=strip_scope,
            indent=get_indent(raw_scope[0]),
        )
        no_skip_range += list(range(start_idx, end))

    result_lines = []
    for line_idx, raw_line in enumerate(raw_code_lines):

        if line_idx not in no_skip_range:
            result_lines.append(raw_line)
            continue

        if line_idx not in scopes_by_idx:
            continue

        scoped = scopes_by_idx[line_idx]
        code_line, meta = fstringify_code("\n".join(scoped["strip_scope"]))

        if not meta["changed"]:
            if debug:
                print("~~~~NOT CHANGED", scoped["raw_scope"], "meta", meta)
            result_lines += scoped["raw_scope"]
            continue

        code_line = force_double_quote_fstring(code_line)
        code_line_parts = code_line.strip().split("\n")

        indie = ""
        indent = scoped["indent"]
        for idx, cline in enumerate(code_line_parts):
            code_line_strip = cline.lstrip()  # if change_add else cline
            if idx == 0:
                indie = indent + code_line_strip
            else:
                if (
                    indie.endswith(",")
                    or indie.endswith("else")
                    or indie.endswith("for")
                    or indie.endswith("in")
                    or indie.endswith("not")
                ):
                    indie += " "

                indie += cline.strip()
                # else:
                #     indie += cline.strip()

        result_lines.append(indie)

    final_code = "\n".join(result_lines)
    return final_code


def skip_file(fn):
    """use tokenizer to make a fancier
        `"s%" not in contents`
    """
    # fn = io.BytesIO(fn.encode("utf-8")).readline
    with open(fn, "rb") as f:
        try:
            g = tokenize.tokenize(f.readline)
            for toknum, tokval, _, _, _ in g:
                if toknum == 53 and tokval == "%":
                    return False
        except tokenize.TokenError:
            pass

        return True
