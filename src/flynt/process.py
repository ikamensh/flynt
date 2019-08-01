from typing import Tuple
from flynt.transform import transform_chunk
from flynt import lexer
from flynt.exceptions import FlyntException
import math

# class JoinTransformer:
#     def __init__(self, code: str, transform_multiline, len_limit):
#         self.result_pieces = []
#         self.count_expressions = 0
#         self.code_in = code
#         self.raw_code_lines = code.split("\n")
#
#         if len_limit is None:
#             len_limit = math.inf
#
#         self.len_limit = len_limit
#         self.transform_multiline = transform_multiline
#
#         self.processed_line = 0
#         self.processed_idx = None
#         self.used_up = False
#
#     def fstringify_code_by_line(self):


def fstringify_code_by_line(code: str, transform_multiline = True, len_limit = 79) -> Tuple[str, int]:
    """ returns fstringified version of the code and amount of lines edited."""

    if len_limit is None:
        len_limit = math.inf

    if transform_multiline:
        lexer.set_multiline()
    else:
        lexer.set_single_line()

    count_expressions = 0

    result_pieces = []
    raw_code_lines = code.split("\n")

    processed_line = 0
    processed_idx = None

    for chunk in lexer.get_fstringify_chunks(code):

        start_line, start_idx, end_idx = chunk.start_line, chunk.start_idx, chunk.end_idx
        line = raw_code_lines[start_line]

        if processed_idx is None:

            while processed_line < start_line:
                result_pieces.append(raw_code_lines[processed_line] + '\n')
                processed_line += 1

            result_pieces.append(line[:start_idx])
            processed_idx = start_idx
        else:
            if start_line == processed_line:
                result_pieces.append(raw_code_lines[processed_line][processed_idx:start_idx])
                processed_idx = start_idx
            else:
                result_pieces.append(raw_code_lines[processed_line][processed_idx:]+'\n')
                processed_line += 1

                while processed_line < start_line:
                    result_pieces.append(raw_code_lines[processed_line] + '\n')
                    processed_line += 1

                result_pieces.append(line[:start_idx])
                processed_idx = None


        contract_lines = chunk.n_lines - 1
        if contract_lines == 0:
            rest = line[end_idx:]
        else:
            next_line = raw_code_lines[start_line + contract_lines]
            rest = next_line[end_idx:]

        try:
            quote_type = chunk.tokens[0].get_quote_type()
        except FlyntException:
            pass
        else:
            converted, meta = transform_chunk(str(chunk), quote_type=quote_type)
            if meta['changed']:
                # if we use multiline, we either transform a single long line,
                # or multiple with result within the limit
                multiline_condition = (
                        not contract_lines
                        or len( "".join([converted, rest]) ) <= len_limit - start_idx
                )
                if multiline_condition:
                    result_pieces.append(converted)
                    count_expressions += 1
                    processed_line += contract_lines
                    processed_idx = end_idx

    if processed_idx is not None:
        result_pieces.append(raw_code_lines[processed_line][processed_idx:] + '\n')
        processed_line += 1

    while len(raw_code_lines) > processed_line:
        result_pieces.append(raw_code_lines[processed_line] + '\n')
        processed_line += 1

    return "".join(result_pieces)[:-1], count_expressions  #last new line is extra.



