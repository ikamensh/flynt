""" Test str processors on actual file contents """
import sys
from test.integration.utils import concat_samples, try_on_file

import pytest

from flynt.code_editor import fstringify_code_by_line, fstringify_concats
from flynt.utils.state import State


def fstringify_and_concats(code: str):
    state = State()
    code, count_a = fstringify_code_by_line(code, state=state)
    code, count_b = fstringify_concats(code, state=state)
    return code, count_a + count_b


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
@pytest.mark.parametrize("filename_concat", concat_samples)
def test_fstringify_concat(filename_concat):
    out, expected = try_on_file(
        filename_concat,
        fstringify_and_concats,
        suffix="_concat",
    )
    assert out == expected
