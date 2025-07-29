import logging
import re
import string
import sys
from functools import lru_cache
from typing import Callable, List, Optional, Tuple

from flynt.candidates.ast_call_candidates import call_candidates
from flynt.candidates.ast_chunk import AstChunk
from flynt.candidates.ast_percent_candidates import percent_candidates
from flynt.exceptions import FlyntException
from flynt.state import State
from flynt.static_join.candidates import join_candidates
from flynt.static_join.transformer import transform_join
from flynt.string_concat.candidates import concat_candidates
from flynt.string_concat.transformer import transform_concat
from flynt.transform.transform import transform_chunk
from flynt.utils.format import QuoteTypes as qt
from flynt.utils.format import get_quote_type, get_string_prefix
from flynt.utils.utils import (
    apply_unicode_escape_map,
    contains_comment,
    unicode_escape_map,
)

noqa_regex = re.compile("#[ ]*noqa.*flynt")
flynt_skip_regex = re.compile(r"#\s*flynt:\s*skip")

log = logging.getLogger(__name__)


class CodeEditor:
    """CodeEditor applies local edits, and keeps most of the original code.

    As parsing and unparsing a file risks unintended changes ( escaped chars,
    formatting quirks, etc.), we try to keep most characters of the original,
    and only inject our edits on relevant locations.

    This class uses variable functions to identify candidate edit locations,
    tries to apply edits on candidates. The candidates factory must return candidates in
    the same order as they occur in the code (first line to last line, left to right chars).
    Given this property, whenever we decide to transform each candidate or not, we can
    add all code to the left of candidate to the result as there will be no edits there;
    and then append the optionally transformed candidate expression. After processing last
    candidate, we can add the rest of the file.
    """

    def __init__(
        self,
        code: str,
        len_limit: Optional[int],
        candidates_iter_factory: Callable,
        transform_func: Callable,
        state: State,
    ) -> None:
        if len_limit is None:
            len_limit = sys.maxsize

        self.len_limit = len_limit
        self.candidates_iter = candidates_iter_factory(code, state)
        self.transform_func = transform_func
        self.state = state
        self.src_lines = code.split("\n")
        self._src_lines_bytes = [line.encode("utf-8") for line in self.src_lines]

        self.results: List[str] = []
        self.count_expressions = 0

        self.last_line = 0
        self.last_idx = 0
        self.used_up = False
        self.output: Optional[str] = None

    def _byte_to_char_idx(self, line_no: int, byte_idx: int) -> int:
        line_bytes = self._src_lines_bytes[line_no]
        return len(line_bytes[:byte_idx].decode("utf-8"))

    def edit(self) -> Tuple[str, int]:
        """Apply edits to the original code."""
        assert not self.used_up, "Tried to use JT twice."
        for chunk in self.candidates_iter:
            self.fill_up_to(chunk)
            self.try_chunk(chunk)

        self.add_rest()
        self.used_up = True
        self.output = "".join(self.results)[:-1]
        return self.output, self.count_expressions

    def code_between(
        self, start_line: int, start_idx: int, end_line: int, end_idx: int
    ) -> str:
        """get source code in the original between two locations."""
        assert end_line >= start_line
        result = []
        if start_line == end_line:
            assert end_idx >= start_idx
            s = self._byte_to_char_idx(start_line, start_idx)
            e = self._byte_to_char_idx(end_line, end_idx)
            result.append(self.src_lines[start_line][s:e])
        else:
            s = self._byte_to_char_idx(start_line, start_idx)
            result.append(self.src_lines[start_line][s:])
            full_lines = range(start_line + 1, end_line)
            for line in full_lines:
                result.append(self.src_lines[line])
            e = self._byte_to_char_idx(end_line, end_idx)
            result.append(self.src_lines[end_line][:e])
        return "\n".join(result)

    @lru_cache(None)
    def code_in_chunk(self, chunk: AstChunk):
        return self.code_between(
            chunk.start_line, chunk.start_idx, chunk.end_line, chunk.end_idx
        )

    def fill_up_to(self, chunk: AstChunk) -> None:
        start_line, start_idx, _ = (
            chunk.start_line,
            self._byte_to_char_idx(chunk.start_line, chunk.start_idx),
            chunk.end_idx,
        )
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

    def fill_up_to_line(self, line: int) -> None:
        while self.last_line < line:
            self.results.append(self.src_lines[self.last_line] + "\n")
            self.last_line += 1

    def try_chunk(self, chunk: AstChunk) -> None:
        """Try applying a transform to a chunk of code.

        Transformation function is free to decide to refuse conversion,
        e.g. in edge cases that are not supported."""

        # if a chunk has a comment in it, we should abort.
        if contains_comment(self.code_in_chunk(chunk)):
            return

        snippet = self.code_in_chunk(chunk)
        stripped = snippet.lstrip()
        prefix_match = re.match(r"[furbFURB]*(['\"]{3}|['\"])", stripped)
        if prefix_match:
            prefix = get_string_prefix(stripped)
            if "b" in prefix.lower():
                return
            is_raw = "r" in prefix.lower()
        else:
            prefix = ""
            is_raw = False

        # skip lines with # noqa comment or # flynt: skip
        for line in self.src_lines[chunk.start_line : chunk.end_line + 1]:
            if noqa_regex.findall(line) or flynt_skip_regex.findall(line):
                return

        # try/except only needed for python 3.9 due to quote issues
        try:
            quote_type = get_quote_type(snippet)
            escape_map = unicode_escape_map(snippet)
        except FlyntException:
            quote_type = qt.double
            escape_map = {}

        converted, changed = self.transform_func(
            chunk.node, state=self.state, quote_type=quote_type
        )
        if changed and escape_map and not is_raw:
            converted = apply_unicode_escape_map(converted, escape_map)
        if changed:
            contract_lines = chunk.n_lines - 1
            if contract_lines == 0:
                line = self.src_lines[chunk.start_line]
                end_c = self._byte_to_char_idx(chunk.start_line, chunk.end_idx)
                rest = line[end_c:]
            else:
                next_line = self.src_lines[chunk.start_line + contract_lines]
                end_c = self._byte_to_char_idx(
                    chunk.start_line + contract_lines, chunk.end_idx
                )
                rest = next_line[end_c:]
            self.maybe_replace(chunk, contract_lines, converted, rest, is_raw)

    def maybe_replace(
        self,
        chunk: AstChunk,
        contract_lines: int,
        converted: str,
        rest: str,
        is_raw: bool,
    ) -> None:
        """Given a possible edit, see if we want to apply it.

        For example, we might not want to change multiple lines."""
        if contract_lines:
            try:
                snippet_quote = get_quote_type(self.code_in_chunk(chunk))
            except FlyntException:
                snippet_quote = None

            if snippet_quote in (
                qt.triple_double,
                qt.triple_single,
            ):
                lines = converted.split("\\n")
                lines[-1] += rest
                lines_fit = all(
                    len(line)
                    <= self.len_limit
                    - self._byte_to_char_idx(chunk.start_line, chunk.start_idx)
                    for line in lines
                )
                converted = converted.replace("\\n", "\n")
            else:
                lines_fit = len(
                    f"{converted}{rest}"
                ) <= self.len_limit - self._byte_to_char_idx(
                    chunk.start_line, chunk.start_idx
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

        if is_raw:
            converted = converted.replace("\\\\", "\\")
            if not converted.startswith(("r", "R")):
                converted = "r" + converted

        self.results.append(converted)
        self.count_expressions += 1
        self.last_line += contract_lines
        self.last_idx = self._byte_to_char_idx(chunk.end_line, chunk.end_idx)

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


def fstring_candidates(code, state):
    chunks = percent_candidates(code, state) + call_candidates(code, state)
    chunks.sort(key=lambda c: (c.start_line, c.start_idx))
    return chunks


def fstringify_code_by_line(code: str, state: State) -> Tuple[str, int]:
    """returns fstringified version of the code and amount of lines edited."""

    return _transform_code(
        code,
        fstring_candidates,
        transform_chunk,
        state,
    )


def fstringify_concats(code: str, state: State) -> Tuple[str, int]:
    """replace string literal concatenations with f-string expressions."""
    return _transform_code(
        code,
        concat_candidates,
        transform_concat,
        state,
    )


def fstringify_static_joins(code: str, state: State) -> Tuple[str, int]:
    """replace joins on static content with f-string expressions."""
    return _transform_code(
        code,
        join_candidates,
        transform_join,
        state,
    )


def _transform_code(
    code: str,
    candidates_iter_factory: Callable,
    transform_func: Callable,
    state: State,
) -> Tuple[str, int]:
    """returns fstringified version of the code and amount of lines edited."""
    return CodeEditor(
        code,
        state.len_limit,
        candidates_iter_factory,
        transform_func,
        state,
    ).edit()
