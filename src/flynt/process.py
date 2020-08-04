import math
import re
import traceback
from typing import Callable, Tuple
import string

from flynt import lexer, state
from flynt.exceptions import FlyntException
from flynt.format import QuoteTypes as qt
from flynt.format import get_quote_type
from flynt.lexer import split
from flynt.transform.transform import transform_chunk
from flynt.string_concat import concat_candidates, transform_concat

noqa_regex = re.compile("#[ ]*noqa.*flynt")


class JoinTransformer:
    """ JoinTransformer fills up the resulting code by tracking
    the last line number and char index. Failed transformations do not need to do anything -
    not adding results is safe, as original code will be filled in."""

    def __init__(
        self,
        code: str,
        len_limit: int,
        candidates_iter_factory: Callable,
        transform_func: Callable,
    ):

        if len_limit is None:
            len_limit = math.inf

        self.len_limit = len_limit
        self.candidates_iter = candidates_iter_factory(code)
        self.transform_func = transform_func
        self.src_lines = code.split("\n")

        self.results = []
        self.count_expressions = 0

        self.last_line = 0
        self.last_idx = 0
        self.used_up = False

    def fstringify_code_by_line(self):
        assert not self.used_up, "Tried to use JT twice."
        for chunk in self.candidates_iter:
            self.fill_up_to(chunk)
            self.try_chunk(chunk)

        self.add_rest()
        self.used_up = True
        return "".join(self.results)[:-1], self.count_expressions

    def fill_up_to(self, chunk):
        start_line, start_idx, _ = (chunk.start_line, chunk.start_idx, chunk.end_idx)
        line = self.src_lines[start_line]

        if start_line == self.last_line:
            self.results.append(
                self.src_lines[self.last_line][self.last_idx : start_idx]
            )
        else:
            self.results.append(self.src_lines[self.last_line][self.last_idx :] + "\n")
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

        try:
            if chunk.string_in_string:
                quote_type = qt.double
            else:
                quote_type = chunk.quote_type

        except FlyntException as e:
            if state.verbose:
                print(f"Exception {e} during conversion of code '{str(chunk)}'")
                traceback.print_exc()

        else:
            converted, changed = self.transform_func(str(chunk), quote_type=quote_type)
            if changed:
                contract_lines = chunk.n_lines - 1
                if contract_lines == 0:
                    line = self.src_lines[chunk.start_line]
                    rest = line[chunk.end_idx :]
                else:
                    next_line = self.src_lines[chunk.start_line + contract_lines]
                    rest = next_line[chunk.end_idx :]
                self.maybe_replace(chunk, contract_lines, converted, rest)

    def maybe_replace(self, chunk, contract_lines, converted, rest):
        if contract_lines:
            if get_quote_type(str(chunk)) in (qt.triple_double, qt.triple_single):
                lines = converted.split("\\n")
                lines[-1] += rest
                lines_fit = all(
                    len(l) <= self.len_limit - chunk.start_idx for l in lines
                )
                converted = converted.replace("\\n", "\n")
            else:
                lines_fit = (
                    len("".join([converted, rest])) <= self.len_limit - chunk.start_idx
                )

        else:
            lines_fit = True
        if not contract_lines or lines_fit:

            self.results.append(converted)
            self.count_expressions += 1
            self.last_line += contract_lines
            self.last_idx = chunk.end_idx

            # remove redundant parenthesis
            if len(self.results) < 2 or not self.results[-2]:
                return
            elif len(self.src_lines[self.last_line]) == self.last_idx:
                return

            if (
                self.results[-2][-1] == "("
                and self.src_lines[self.last_line][self.last_idx] == ")"
            ):
                for char in reversed(self.results[-2][:-1]):
                    if char in string.whitespace:
                        continue
                    elif char in "(=[+*":
                        break
                    else:
                        return

                self.results[-2] = self.results[-2][:-1]
                self.last_idx += 1

    def add_rest(self):
        self.results.append(self.src_lines[self.last_line][self.last_idx :] + "\n")
        self.last_line += 1

        while len(self.src_lines) > self.last_line:
            self.results.append(self.src_lines[self.last_line] + "\n")
            self.last_line += 1


def fstringify_code_by_line(code: str, multiline=True, len_limit=88) -> Tuple[str, int]:
    """ returns fstringified version of the code and amount of lines edited."""
    return _transform_code(
        code, split.get_fstringify_chunks, transform_chunk, multiline, len_limit
    )


def fstringify_concats(code: str, multiline=True, len_limit=88) -> Tuple[str, int]:
    """ replace string literal concatenations with f-string expressions. """
    return _transform_code(
        code, concat_candidates, transform_concat, multiline, len_limit
    )


def _transform_code(
    code: str, candidates_iter_factory, transform_func, multiline, len_limit
) -> Tuple[str, int]:
    """ returns fstringified version of the code and amount of lines edited."""

    len_limit = _multiline_settings(len_limit, multiline)
    jt = JoinTransformer(code, len_limit, candidates_iter_factory, transform_func)
    return jt.fstringify_code_by_line()


def _multiline_settings(len_limit, multiline):
    if not multiline:
        len_limit = 0
        lexer.set_single_line()
    else:
        lexer.set_multiline()
    return len_limit
