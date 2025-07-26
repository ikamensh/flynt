import pytest
from functools import partial
from test.integration.utils import try_on_file
from flynt.code_editor import fstringify_code_by_line

SAMPLES = ["escaped_newline.py"]


@pytest.mark.parametrize("filename", SAMPLES)
@pytest.mark.xfail(reason="newline escapes not preserved (#83)")
def test_newline_escape(filename, state):
    out, expected = try_on_file(
        filename,
        partial(fstringify_code_by_line, state=state),
    )
    assert out == expected
