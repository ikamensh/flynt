import io
import tokenize
import traceback
from typing import Generator

from flynt import state
from flynt.lexer.Chunk import Chunk
from flynt.lexer.PyToken import PyToken


def get_chunks(code) -> Generator[Chunk, None, None]:
    g = tokenize.tokenize(io.BytesIO(code.encode("utf-8")).readline)
    chunk = Chunk()

    try:
        for item in g:
            t = PyToken(item)
            reuse = chunk.append(t)

            if chunk.complete:

                yield chunk
                chunk = Chunk()
                if reuse:
                    reuse = chunk.append(t)
                    # assert not reuse
                    if chunk.complete:
                        yield chunk
                        chunk = Chunk()

        yield chunk
    except tokenize.TokenError as e:
        if state.verbose:
            traceback.print_exc()
            print(e)


def get_fstringify_chunks(code: str) -> Generator[Chunk, None, None]:
    """
    A generator yielding Chunks of the code where fstring can be formed.
    """
    last_concat = False

    for chunk in get_chunks(code):
        if chunk.successful and not last_concat:
            yield chunk

        if len(chunk) and chunk[-1].is_string():
            last_concat = True
        else:
            if Chunk.multiline or len(chunk) > 0:
                last_concat = False
