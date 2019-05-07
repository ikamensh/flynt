from fstringify.transform import fstringify_code
from fstringify.lexer import get_fstringify_lines

def fstringify_code_by_line(code: str):

    current_line = 0
    result_pieces = []

    raw_code_lines = code.split("\n")

    for line, end_idx in get_fstringify_lines(code):
        # for start, end in positions:

        start_idx = line - 1
        while current_line < start_idx:
            result_pieces.append(raw_code_lines[current_line]+'\n')
            current_line += 1

        line = raw_code_lines[start_idx]

        to_process, rest = line[:end_idx], line[end_idx:]
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


