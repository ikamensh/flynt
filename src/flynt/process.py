from typing import Tuple, Callable
import math
import re

from flynt.transform.transform import transform_chunk
from flynt import lexer
from flynt.lexer import split
from flynt.exceptions import FlyntException
from flynt.format import QuoteTypes


noqa_regex = re.compile("#[ ]*noqa.*flynt")


class JoinTransformer:
    """ JoinTransformer fills up the resulting code by tracking
    the last line number and char index. Failed transformations do not need to do anything -
    not adding results is safe, as original code will be filled in."""

    def __init__(
        self,
        code: str,
        len_limit: int,
        candidates_constructor: Callable = split.get_fstringify_chunks,
        transform_func: Callable = transform_chunk,
    ):

        if len_limit is None:
            len_limit = math.inf

        self.len_limit = len_limit
        self.candidates_generator = candidates_constructor(code)
        self.transform_func = transform_func
        self.src_lines = code.split("\n")

        self.results = []
        self.count_expressions = 0

        self.last_line = 0
        self.last_idx = None
        self.used_up = False

    def fstringify_code_by_line(self):
        assert not self.used_up, "Tried to use JT twice."
        for chunk in self.candidates_generator:
            self.fill_up_to(chunk)
            self.try_chunk(chunk)

        self.add_rest()
        self.used_up = True
        return "".join(self.results)[:-1], self.count_expressions

    def fill_up_to(self, chunk):
        start_line, start_idx, _ = (chunk.start_line, chunk.start_idx, chunk.end_idx)
        line = self.src_lines[start_line]

        if self.last_idx is None:
            self.fill_up_to_line(start_line)
            self.results.append(line[:start_idx])
        else:
            if start_line == self.last_line:
                self.results.append(
                    self.src_lines[self.last_line][self.last_idx : start_idx]
                )
            else:
                self.results.append(
                    self.src_lines[self.last_line][self.last_idx :] + "\n"
                )
                self.last_line += 1
                self.fill_up_to_line(start_line)
                self.results.append(line[:start_idx])

        self.last_idx = start_idx

    def fill_up_to_line(self, start_line):
        while self.last_line < start_line:
            self.results.append(self.src_lines[self.last_line] + "\n")
            self.last_line += 1

    def try_chunk(self, chunk):

        for line in self.src_lines[chunk.start_line : chunk.start_line + chunk.n_lines]:
            if noqa_regex.findall(line):
                # user does not wish for this line to be converted.
                return

        line = self.src_lines[chunk.start_line]

        contract_lines = chunk.n_lines - 1
        if contract_lines == 0:
            rest = line[chunk.end_idx :]
        else:
            next_line = self.src_lines[chunk.start_line + contract_lines]
            rest = next_line[chunk.end_idx :]

        try:
            if chunk.string_in_string:
                quote_type = QuoteTypes.double
            else:
                quote_type = chunk.quote_type

        except FlyntException:
            pass
        else:
            converted, changed = self.transform_func(str(chunk), quote_type=quote_type)
            if changed:
                multiline_condition = (
                    not contract_lines
                    or len("".join([converted, rest]))
                    <= self.len_limit - chunk.start_idx
                )
                if multiline_condition:
                    self.results.append(converted)
                    self.count_expressions += 1
                    self.last_line += contract_lines
                    self.last_idx = chunk.end_idx

    def add_rest(self):
        if self.last_idx is not None:
            self.results.append(self.src_lines[self.last_line][self.last_idx :] + "\n")
            self.last_line += 1

        while len(self.src_lines) > self.last_line:
            self.results.append(self.src_lines[self.last_line] + "\n")
            self.last_line += 1


def fstringify_code_by_line(code: str, multiline=True, len_limit=88) -> Tuple[str, int]:
    """ returns fstringified version of the code and amount of lines edited."""
    if not multiline:
        len_limit = 0
        lexer.set_single_line()
    else:
        lexer.set_multiline()

    jt = JoinTransformer(code, len_limit)

    return jt.fstringify_code_by_line()


from flynt.string_concat import transform_concat, concat_candidates


def fstringify_concats(code: str, multiline=True, len_limit=88) -> Tuple[str, int]:
    """ returns fstringified version of the code and amount of lines edited."""
    if not multiline:
        len_limit = 0
        lexer.set_single_line()
    else:
        lexer.set_multiline()

    jt = JoinTransformer(
        code,
        len_limit,
        candidates_constructor=concat_candidates,
        transform_func=transform_concat,
    )

    return jt.fstringify_code_by_line()
