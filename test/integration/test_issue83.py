from functools import partial

from test.integration.utils import try_on_file
from flynt.code_editor import fstringify_code_by_line


def test_escaped_newline(state):
    out, expected = try_on_file(
        "escaped_newline.py",
        partial(fstringify_code_by_line, state=state),
    )
    assert out == expected
