from typing import Tuple
from flynt.transform import fstringify_code
from flynt.lexer import get_fstringify_lines

def fstringify_code_by_line(code: str) -> Tuple[str, int]:
    """ returns fstringified version of the code and amount of lines edited."""
    count_edits = 0
    current_line = 0
    result_pieces = []

    raw_code_lines = code.split("\n")

    for chunk in get_fstringify_lines(code):

        line_idx, start_idx, end_idx = chunk.line, chunk.start_idx, chunk.end_idx

        while current_line < line_idx:
            result_pieces.append(raw_code_lines[current_line]+'\n')
            current_line += 1

        line = raw_code_lines[line_idx]

        before, to_process, rest = line[:start_idx], line[start_idx:end_idx], line[end_idx:]
        new_line, meta = fstringify_code(to_process, quote_type=chunk.tokens[0].get_quote_type())
        if meta['changed']:
            result_pieces +=[before, new_line, rest+"\n"]
            count_edits += 1
        else:
            result_pieces.append(line+"\n")

        current_line += 1

    while len(raw_code_lines) > current_line:
        result_pieces.append(raw_code_lines[current_line] + '\n')
        current_line += 1

    return "".join(result_pieces)[:-1], count_edits  #last new line is extra.



