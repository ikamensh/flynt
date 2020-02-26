import os
import ast
import sys

import pytest


@pytest.fixture()
def pycode_with_2_concats():
    folder = os.path.dirname(__file__)
    path = os.path.join(folder, "victim.py")
    with open(path) as f:
        content = f.read()

    yield content


from flynt.string_concat.candidates import ConcatHound, concat_candidates


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
def test_find_victims_primitives(pycode_with_2_concats: str):
    tree = ast.parse(pycode_with_2_concats)

    ch = ConcatHound()
    ch.visit(tree)

    assert len(ch.victims) == 2

    v1, v2 = ch.victims
    assert str(v1) == "a + ' World'"
    assert 'a + " World"' in pycode_with_2_concats.split("\n")[v1.start_line]


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
def test_find_victims_api(pycode_with_2_concats: str):
    gen = concat_candidates(pycode_with_2_concats)
    lst = list(gen)

    assert len(lst) == 2

    v1, v2 = lst
    assert str(v1) == "a + ' World'"
    assert 'a + " World"' in pycode_with_2_concats.split("\n")[v1.start_line]


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
def test_find_victims_api():
    txt_in = """print('blah' + (thing - 1))"""
    gen = concat_candidates(txt_in)
    lst = list(gen)

    assert len(lst) == 1

    v1 = lst[0]
    assert str(v1) == """'blah' + (thing - 1)"""
