""" Test str processors on actual file contents """
from functools import partial

from flynt.process import fstringify_code_by_line
from test.integration.utils import try_on_file


def test_fstringify(filename):
    out, expected = try_on_file(
        filename,
        partial(fstringify_code_by_line, multiline=True, len_limit=None),
    )
    assert out == expected


def test_fstringify_single_line(filename):
    out, expected = try_on_file(
        filename,
        partial(fstringify_code_by_line, multiline=False, len_limit=None),
        out_suffix="_single_line",
    )
    assert out == expected
