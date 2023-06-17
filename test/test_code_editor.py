import pytest

from flynt.candidates.ast_percent_candidates import percent_candidates
from flynt.code_editor import CodeEditor
from flynt.utils.state import State

s0 = """'%s' % (
                    v['key'])"""
s1 = """\"%(a)-6d %(a)s" % d"""


@pytest.mark.parametrize(
    "s_in",
    [s0, s1],
)
def test_code_between_exact(s_in):
    chunk = set(percent_candidates(s_in, State())).pop()
    editor = CodeEditor(s_in, None, lambda *args: None, None)

    assert editor.code_in_chunk(chunk) == s_in
