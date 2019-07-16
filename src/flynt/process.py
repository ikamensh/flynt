from typing import Tuple
from flynt.transform import transform_chunk
from flynt.lexer import get_fstringify_chunks, set_multiline, set_single_line
import math

def fstringify_code_by_line(code: str, transform_multiline = True, len_limit = 79) -> Tuple[str, int]:
    """ returns fstringified version of the code and amount of lines edited."""

    if len_limit is None:
        len_limit = math.inf

    if transform_multiline:
        set_multiline()
    else:
        set_single_line()

    count_expressions = 0
    current_line = 0
    result_pieces = []

    raw_code_lines = code.split("\n")

    for chunk in get_fstringify_chunks(code):

        line_idx, start_idx, end_idx = chunk.line, chunk.start_idx, chunk.end_idx
        contract_lines = chunk.n_lines - 1

        while current_line < line_idx:
            result_pieces.append(raw_code_lines[current_line]+'\n')
            current_line += 1

        line = raw_code_lines[line_idx]
        next_line = raw_code_lines[line_idx + contract_lines]

        before = line[:start_idx]
        if contract_lines == 0:
            to_process = line[start_idx:end_idx]
            rest = line[end_idx:]
        elif contract_lines == 1:
            to_process = line[start_idx:] + next_line[:end_idx]
            rest = next_line[end_idx:]
        else:
            to_process = line[start_idx:]
            for i in range(1, contract_lines):
                to_process += raw_code_lines[line_idx + i]
            to_process += next_line[:end_idx]
            rest = next_line[end_idx:]

        processed, meta = transform_chunk(str(chunk), quote_type=chunk.tokens[0].get_quote_type())
        if meta['changed'] and len( "".join([before, processed, rest]) ) <= len_limit:
            result_pieces +=[before, processed, rest+"\n"]
            count_expressions += 1
            current_line += (1 + contract_lines)

    while len(raw_code_lines) > current_line:
        result_pieces.append(raw_code_lines[current_line] + '\n')
        current_line += 1

    return "".join(result_pieces)[:-1], count_expressions  #last new line is extra.



