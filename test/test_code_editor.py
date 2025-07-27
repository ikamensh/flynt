import pytest

from functools import partial

from flynt.candidates.ast_percent_candidates import percent_candidates
from flynt.candidates.ast_call_candidates import call_candidates
from flynt.code_editor import CodeEditor
from flynt.state import State
from flynt.transform.transform import transform_chunk

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


def test_unicode_offset_translation():
    code = 'print("Feels like: {}°F".format(data["main"]["feels_like"]))'
    state = State()
    chunk = next(iter(call_candidates(code, state)))
    editor = CodeEditor(
        code,
        state.len_limit,
        lambda _=None: [chunk],
        partial(transform_chunk, state=state),
    )
    out, count = editor.edit()
    assert out == "print(f\"Feels like: {data['main']['feels_like']}°F\")"
    assert count == 1
