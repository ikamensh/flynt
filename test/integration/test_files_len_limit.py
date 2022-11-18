""" Test str processors on actual file contents """
from functools import partial

import pytest

from flynt.process import fstringify_concats
from test.integration.utils import try_on_file


@pytest.mark.parametrize("filename", ["multiline_limit.py"])
def test_fstringify(filename):
    out, expected = try_on_file(
        filename,
        partial(fstringify_concats, multiline=True, len_limit=None),
    )
    assert out == expected
