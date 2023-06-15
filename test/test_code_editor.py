import pytest

from flynt.candidates import split
from flynt.code_editor import CodeEditor
from flynt.format import get_quote_type

s0 = """'%s' % (
                    v['key'])"""
s1 = """s = '%s' % (
                    v['key'])"""

s2 = """\"%(a)-6d %(a)s" % d"""


@pytest.mark.parametrize(
    "s_in",
    [
        s1, s2
    ],
)
def test_code_between_qoute_types(s_in):

    chunk = set(split.get_fstringify_chunks(s_in)).pop()
    editor = CodeEditor(s_in, None, lambda *args: None, None)

    assert get_quote_type(editor.code_in_chunk(chunk)) == get_quote_type(str(chunk))


@pytest.mark.parametrize(
    "s_in",
    [
        s0, s2
    ],
)
def test_code_between_exact(s_in):
    chunk = set(split.get_fstringify_chunks(s_in)).pop()
    editor = CodeEditor(s_in, None, lambda *args: None, None)

    assert editor.code_in_chunk(chunk) == s_in
