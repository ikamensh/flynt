import dataclasses
import token
from typing import FrozenSet


@dataclasses.dataclass(frozen=True)
class LexerContext:
    skip_tokens: FrozenSet[int]
    break_tokens: FrozenSet[int]
    multiline: bool


single_line_context = LexerContext(
    skip_tokens=frozenset(),
    break_tokens=frozenset((token.COMMENT, token.NEWLINE, token.NL)),
    multiline=False,
)

multi_line_context = LexerContext(
    skip_tokens=frozenset((token.NEWLINE, token.NL)),
    break_tokens=frozenset((token.COMMENT,)),
    multiline=True,
)
