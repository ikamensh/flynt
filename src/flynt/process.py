from typing import Tuple
from flynt.transform import transform_chunk
from flynt import lexer
from flynt.exceptions import FlyntException
import math

class JoinTransformer:
    """ JoinTransformer fills up the resulting code by tracking
    the last line number and char index. Failed transformations do not need to do anything -
    not adding results is safe, as original code will be filled in."""

    def __init__(self, code: str, len_limit):
        self.results = []
        self.count_expressions = 0
        self.code_in = code
        self.src_lines = code.split("\n")

        if len_limit is None:
            len_limit = math.inf

        self.len_limit = len_limit

        self.last_line = 0
        self.last_idx = None
        self.used_up = False

    def fstringify_code_by_line(self):
        assert not self.used_up, "Tried to use JT twice."
        for chunk in lexer.get_fstringify_chunks(self.code_in):
            self.fill_up_to(chunk)
            self.try_chunk(chunk)

        self.add_rest()
        self.used_up = True
        return "".join(self.results)[:-1], self.count_expressions

    def fill_up_to(self, chunk):
        start_line, start_idx, end_idx = chunk.start_line, chunk.start_idx, chunk.end_idx
        line = self.src_lines[start_line]

        if self.last_idx is None:
            self.fill_up_to_line(start_line)
            self.results.append(line[:start_idx])
        else:
            if start_line == self.last_line:
                self.results.append(self.src_lines[self.last_line][self.last_idx:start_idx])
            else:
                self.results.append(self.src_lines[self.last_line][self.last_idx:] + '\n')
                self.last_line += 1
                self.fill_up_to_line(start_line)
                self.results.append(line[:start_idx])

        self.last_idx = start_idx

    def fill_up_to_line(self, start_line):
        while self.last_line < start_line:
            self.results.append(self.src_lines[self.last_line] + '\n')
            self.last_line += 1

    def try_chunk(self, chunk):
        start_line, start_idx, end_idx = chunk.start_line, chunk.start_idx, chunk.end_idx
        line = self.src_lines[start_line]

        contract_lines = chunk.n_lines - 1
        if contract_lines == 0:
            rest = line[end_idx:]
        else:
            next_line = self.src_lines[start_line + contract_lines]
            rest = next_line[end_idx:]

        try:
            quote_type = chunk.tokens[0].get_quote_type()
        except FlyntException:
            pass
        else:
            converted, meta = transform_chunk(str(chunk), quote_type=quote_type)
            if meta['changed']:
                multiline_condition = (
                        not contract_lines
                        or len( "".join([converted, rest]) ) <= self.len_limit - start_idx
                )
                if multiline_condition:
                    self.results.append(converted)
                    self.count_expressions += 1
                    self.last_line += contract_lines
                    self.last_idx = end_idx

    def add_rest(self):
        if self.last_idx is not None:
            self.results.append(self.src_lines[self.last_line][self.last_idx:] + '\n')
            self.last_line += 1

        while len(self.src_lines) > self.last_line:
            self.results.append(self.src_lines[self.last_line] + '\n')
            self.last_line += 1


def fstringify_code_by_line(code: str, multiline = True, len_limit = 79) -> Tuple[str, int]:
    """ returns fstringified version of the code and amount of lines edited."""
    if not multiline:
        len_limit = 0
        lexer.set_single_line()
    else:
        lexer.set_multiline()

    jt = JoinTransformer(code, len_limit)

    return jt.fstringify_code_by_line()



