import io
import tokenize
from typing import Generator

from flynt.lexer.chunk import Chunk
from flynt.lexer.py_token import PyToken


def get_chunks(code) -> Generator[Chunk, None, None]:
    token_line = tokenize.tokenize(io.BytesIO(code.encode("utf-8")).readline)
    chunk = Chunk()

    for item in token_line:
        py_token = PyToken(item)
        reuse = chunk.append(py_token)

        if chunk.complete:

            yield chunk
            chunk = Chunk()
            if reuse:
                reuse = chunk.append(py_token)
                # assert not reuse
                if chunk.complete:
                    yield chunk
                    chunk = Chunk()

    yield chunk


def get_fstringify_chunks(code: str) -> Generator[Chunk, None, None]:
    """
    A generator yielding Chunks of the code where fstring can be formed.
    """
    last_concat = False

    for chunk in get_chunks(code):
        if chunk.successful and not last_concat:
            yield chunk

        if chunk and chunk[-1].is_string():
            last_concat = True
        else:
            if Chunk.multiline or chunk:
                last_concat = False
