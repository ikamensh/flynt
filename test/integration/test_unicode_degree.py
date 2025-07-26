from functools import partial
from test.integration.utils import try_on_file
from flynt.code_editor import fstringify_code_by_line


def test_unicode_degree(state):
    out, expected = try_on_file(
        "unicode_degree.py",
        partial(fstringify_code_by_line, state=state),
    )
    assert out == expected
