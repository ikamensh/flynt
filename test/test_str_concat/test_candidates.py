import os
import ast

import pytest


@pytest.fixture()
def pycode_with_2_concats():
    folder = os.path.dirname(__file__)
    path = os.path.join(folder, "victim.py")
    with open(path) as f:
        content = f.read()

    yield content


from flynt.string_concat.candidates import ConcatHound


def test_find_victims(pycode_with_2_concats: str):
    tree = ast.parse(pycode_with_2_concats)

    ch = ConcatHound()
    ch.visit(tree)

    assert len(ch.victims) == 2

    for victim in ch.victims:
        print(
            victim.lineno, victim.col_offset, victim.end_lineno, victim.end_col_offset
        )
