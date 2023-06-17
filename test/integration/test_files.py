""" Test str processors on actual file contents """
from functools import partial
from test.integration.utils import samples, try_on_file

import pytest

from flynt.code_editor import fstringify_code_by_line
from flynt.utils.state import State


@pytest.mark.parametrize("filename", samples)
def test_fstringify(filename, state):
    out, expected = try_on_file(
        filename,
        partial(fstringify_code_by_line, state=state),
    )
    assert out == expected


@pytest.mark.parametrize("filename", samples)
def test_fstringify_single_line(filename):
    state = State(multiline=False)
    out, expected = try_on_file(
        filename,
        partial(fstringify_code_by_line, state=state),
        out_suffix="_single_line",
    )
    assert out == expected


@pytest.mark.parametrize("enable", ["percent_only", "format_only"])
def test_fstringify_enables(enable):
    state = State(
        multiline=False,
        len_limit=None,
        transform_percent=(enable == "percent_only"),
        transform_format=(enable == "format_only"),
    )
    out, expected = try_on_file(
        "sample.py",
        partial(
            fstringify_code_by_line,
            state=state,
        ),
        suffix="_enable",
        out_suffix=f"_enable_{enable}",
    )
    assert out == expected
