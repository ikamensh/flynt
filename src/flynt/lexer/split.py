import io
import logging
import tokenize
from typing import Generator

from flynt.lexer.Chunk import Chunk
from flynt.lexer.context import LexerContext, multi_line_context
from flynt.lexer.PyToken import PyToken

log = logging.getLogger(__name__)


def get_chunks(
    code: str,
    *,
    lexer_context: LexerContext,
) -> Generator[Chunk, None, None]:
    g = tokenize.tokenize(io.BytesIO(code.encode("utf-8")).readline)
    chunk = Chunk(lexer_context=lexer_context)

    try:
        for item in g:
            t = PyToken(item)
            reuse = chunk.append(t)

            if chunk.complete:

                yield chunk
                chunk = Chunk(lexer_context=lexer_context)
                if reuse:
                    reuse = chunk.append(t)
                    # assert not reuse
                    if chunk.complete:
                        yield chunk
                        chunk = Chunk(lexer_context=lexer_context)

        yield chunk
    except tokenize.TokenError as e:
        log.error(
            f"TokenError: {e}",
            exc_info=True,
        )


def get_fstringify_chunks(
    code: str,
    lexer_context: LexerContext = multi_line_context,
) -> Generator[Chunk, None, None]:
    """
    A generator yielding Chunks of the code where fstring can be formed.
    """
    last_concat = False

    for chunk in get_chunks(code, lexer_context=lexer_context):
        if chunk.successful and not last_concat:
            yield chunk

        if len(chunk) and chunk[-1].is_string():
            last_concat = True
        else:
            if lexer_context.multiline or len(chunk) > 0:
                last_concat = False
