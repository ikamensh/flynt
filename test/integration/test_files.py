""" Test str processors on actual file contents """
from functools import partial
from test.integration.utils import samples, try_on_file

import pytest

from flynt.process import fstringify_code_by_line


@pytest.mark.parametrize("filename", samples)
def test_fstringify(filename):
    out, expected = try_on_file(
        filename,
        partial(fstringify_code_by_line, multiline=True, len_limit=None),
    )
    assert out == expected


@pytest.mark.parametrize("filename", samples)
def test_fstringify_single_line(filename):
    out, expected = try_on_file(
        filename,
        partial(fstringify_code_by_line, multiline=False, len_limit=None),
        out_suffix="_single_line",
    )
    assert out == expected


@pytest.mark.parametrize("enable", ["percent_only", "format_only"])
def test_fstringify_enables(enable):
    out, expected = try_on_file(
        "sample.py",
        partial(
            fstringify_code_by_line,
            multiline=False,
            len_limit=None,
            transform_percent=(enable == "percent_only"),
            transform_format=(enable == "format_only"),
        ),
        suffix="_enable",
        out_suffix=f"_enable_{enable}",
    )
    assert out == expected
