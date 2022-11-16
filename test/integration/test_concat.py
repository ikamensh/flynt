""" Test str processors on actual file contents """
import sys

import pytest

from flynt.process import fstringify_concats, fstringify_code_by_line
from test.integration.utils import try_on_file


def fstringify_and_concats(code: str):
    code, count_a = fstringify_code_by_line(code, multiline=True, len_limit=None)
    code, count_b = fstringify_concats(code, multiline=True, len_limit=None)
    return code, count_a + count_b


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
def test_fstringify_concat(filename_concat):
    out, expected = try_on_file(
        filename_concat,
        fstringify_and_concats,
        suffix="_concat",
    )
    assert out == expected
