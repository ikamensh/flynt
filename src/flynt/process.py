import logging
import math
import re
import string
from functools import partial
from typing import Callable, List, Optional, Tuple, Union

from flynt import lexer
from flynt.ast_chunk import AstChunk
from flynt.exceptions import FlyntException
from flynt.format import QuoteTypes as qt
from flynt.format import get_quote_type
from flynt.lexer import split
from flynt.lexer.Chunk import Chunk
from flynt.state import State
from flynt.static_join.candidates import join_candidates
from flynt.static_join.transformer import transform_join
from flynt.string_concat.candidates import concat_candidates
from flynt.string_concat.transformer import transform_concat
from flynt.transform.transform import transform_chunk

noqa_regex = re.compile("#[ ]*noqa.*flynt")

log = logging.getLogger(__name__)


class JoinTransformer:
    """JoinTransformer fills up the resulting code by tracking
    the last line number and char index. Failed transformations do not need to do anything -
    not adding results is safe, as original code will be filled in."""

    def __init__(
        self,
        code: str,
        len_limit: Optional[int],
        candidates_iter_factory: Callable,
        transform_func: Callable,
    ) -> None:
        self.len_limit = len_limit if len_limit is not None else math.inf
        self.candidates_iter = candidates_iter_factory(code)
        self.transform_func = transform_func
        self.src_lines = code.split("\n")

        self.results: List[str] = []
        self.count_expressions = 0

        self.last_line = 0
        self.last_idx = 0
        self.used_up = False

    def fstringify_code_by_line(self) -> Tuple[str, int]:
        assert not self.used_up, "Tried to use JT twice."
        for chunk in self.candidates_iter:
            self.fill_up_to(chunk)
            self.try_chunk(chunk)

        self.add_rest()
        self.used_up = True
        return "".join(self.results)[:-1], self.count_expressions

    def fill_up_to(self, chunk: Union[Chunk, AstChunk]) -> None:
        start_line, start_idx, _ = (chunk.start_line, chunk.start_idx, chunk.end_idx)
        if start_line == self.last_line:
            self.results.append(
                self.src_lines[self.last_line][self.last_idx : start_idx],
            )
        else:
            self.results.append(self.src_lines[self.last_line][self.last_idx :] + "\n")
            self.last_line += 1
            line = self.src_lines[start_line]

            self.fill_up_to_line(start_line)
            self.results.append(line[:start_idx])

        self.last_idx = start_idx

    def fill_up_to_line(self, start_line: int) -> None:
        while self.last_line < start_line:
            self.results.append(self.src_lines[self.last_line] + "\n")
            self.last_line += 1

    def try_chunk(self, chunk: Union[Chunk, AstChunk]) -> None:

        for line in self.src_lines[chunk.start_line : chunk.start_line + chunk.n_lines]:
            if noqa_regex.findall(line):
                # user does not wish for this line to be converted.
                return

        try:
            quote_type = (
                qt.double
                if chunk.string_in_string and chunk.n_lines == 1
                else chunk.quote_type
            )
        except FlyntException:
            quote_type = qt.double

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

    def maybe_replace(
        self,
        chunk: Union[Chunk, AstChunk],
        contract_lines: int,
        converted: str,
        rest: str,
    ) -> None:
        if contract_lines:
            if get_quote_type(str(chunk)) in (qt.triple_double, qt.triple_single):
                lines = converted.split("\\n")
                lines[-1] += rest
                lines_fit = all(
                    len(line) <= self.len_limit - chunk.start_idx for line in lines
                )
                converted = converted.replace("\\n", "\n")
            else:
                lines_fit = (
                    len(f"{converted}{rest}") <= self.len_limit - chunk.start_idx
                )

        else:
            lines_fit = True
        if contract_lines and not lines_fit:
            log.warning(
                "Skipping conversion of %s due to line length limit. "
                "Pass -ll 999 to increase it. "
                "(999 is an example, as number of characters.)",
                str(chunk),
            )
            return

        self.results.append(converted)
        self.count_expressions += 1
        self.last_line += contract_lines
        self.last_idx = chunk.end_idx

        # remove redundant parenthesis
        if len(self.results) < 2 or not self.results[-2]:
            return

        if len(self.src_lines[self.last_line]) == self.last_idx:
            return

        if (
            self.results[-2][-1] == "("
            and self.src_lines[self.last_line][self.last_idx] == ")"
        ):
            for char in reversed(self.results[-2][:-1]):
                if char in string.whitespace:
                    continue
                if char in "(=[+*":
                    break
                return

            self.results[-2] = self.results[-2][:-1]
            self.last_idx += 1

    def add_rest(self) -> None:
        self.results.append(self.src_lines[self.last_line][self.last_idx :] + "\n")
        self.last_line += 1

        while len(self.src_lines) > self.last_line:
            self.results.append(self.src_lines[self.last_line] + "\n")
            self.last_line += 1


def fstringify_code_by_line(code: str, state: State) -> Tuple[str, int]:
    """returns fstringified version of the code and amount of lines edited."""
    return _transform_code(
        code,
        split.get_fstringify_chunks,
        partial(transform_chunk, state=state),
        state,
    )


def fstringify_concats(code: str, state: State) -> Tuple[str, int]:
    """replace string literal concatenations with f-string expressions."""
    return _transform_code(
        code,
        partial(concat_candidates, state=state),
        partial(transform_concat, state=state),
        state,
    )


def fstringify_static_joins(code: str, state: State) -> Tuple[str, int]:
    """replace joins on static content with f-string expressions."""
    return _transform_code(
        code,
        partial(join_candidates, state=state),
        partial(transform_join, state=state),
        state,
    )


def _transform_code(
    code: str,
    candidates_iter_factory: Callable,
    transform_func: Callable,
    state: State,
) -> Tuple[str, int]:
    """returns fstringified version of the code and amount of lines edited."""
    len_limit = _multiline_settings(state)
    jt = JoinTransformer(code, len_limit, candidates_iter_factory, transform_func)
    return jt.fstringify_code_by_line()


def _multiline_settings(state: State) -> Optional[int]:
    # TODO: eradicate this function and system
    if not state.multiline:
        state.len_limit = 0
        lexer.set_single_line()
    else:
        lexer.set_multiline()
    return state.len_limit
