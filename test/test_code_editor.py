import pytest


from flynt.candidates.ast_percent_candidates import percent_candidates
from flynt.candidates.ast_call_candidates import call_candidates
from flynt.code_editor import CodeEditor
from flynt.state import State
from flynt.transform.transform import transform_chunk
from flynt.utils.utils import contains_comment

s0 = """'%s' % (
                    v['key'])"""
s1 = """\"%(a)-6d %(a)s" % d"""


@pytest.mark.parametrize(
    "s_in",
    [s0, s1],
)
def test_code_between_exact(s_in):
    state = State()
    chunk = set(percent_candidates(s_in, state)).pop()
    editor = CodeEditor(s_in, None, lambda *args: None, None, state)

    assert editor.code_in_chunk(chunk) == s_in


def test_unicode_offset_translation():
    """Can do successful edits with multi-byte unicode characters."""
    code = 'print("Feels like: {}°F".format(data["main"]["feels_like"]))'
    state = State()
    chunk = next(iter(call_candidates(code, state)))
    editor = CodeEditor(
        code,
        state.len_limit,
        lambda *_: [chunk],
        transform_chunk,
        state,
    )
    out, count = editor.edit()
    assert out == "print(f\"Feels like: {data['main']['feels_like']}°F\")"
    assert count == 1


def test_unicode_chunk_no_token_error():
    """Using multi-byte unicode symbols should not mess with finding right substrings."""
    code = 'print("Feels l°°ike: {}ﭗ°°\u1234F".format(data["main"]["feels_like"]))'
    state = State()
    chunk = next(iter(call_candidates(code, state)))
    editor = CodeEditor(code, None, lambda *_: [chunk], None, state)

    snippet = editor.code_in_chunk(chunk)

    assert snippet == '"Feels l°°ike: {}ﭗ°°\u1234F".format(data["main"]["feels_like"])'
    assert contains_comment(snippet) is False


def test_unicode_escape_preserved():
    """Unicode escaped characters should be kept as such."""
    code = 'print("Feels like: {}\\u00B0F".format(data["main"]["feels_like"]))'
    state = State()
    chunk = next(iter(call_candidates(code, state)))
    editor = CodeEditor(
        code,
        state.len_limit,
        lambda *_: [chunk],
        transform_chunk,
        state,
    )
    out, count = editor.edit()
    assert out == "print(f\"Feels like: {data['main']['feels_like']}\\u00B0F\")"
    assert count == 1


def test_unicode_escape_mixed_preserved():
    """Unicode escaped characters should be kept as such."""
    code = 'print("Feels like: {}\\u00B0F°".format(data["main"]["feels_like"]))'
    state = State()
    chunk = next(iter(call_candidates(code, state)))
    editor = CodeEditor(
        code,
        state.len_limit,
        lambda *_: [chunk],
        transform_chunk,
        state,
    )
    out, count = editor.edit()
    assert out == "print(f\"Feels like: {data['main']['feels_like']}\\u00B0F°\")"
    assert count == 1
