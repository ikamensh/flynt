""" Test str processors on actual file contents """
from functools import partial
from test.integration.utils import try_on_file

import pytest

from flynt.process import fstringify_concats


@pytest.mark.parametrize("filename", ["multiline_limit.py"])
def test_fstringify(filename, state):
    out, expected = try_on_file(
        filename,
        partial(fstringify_concats, state=state),
    )
    assert out == expected
