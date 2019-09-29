import ast
import sys

import pytest

from flynt.string_concat.transformer import unpack_binop, transform_concat


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
def test_unpack():

    txt = """a + 'Hello' + b + 'World'"""
    node = ast.parse(txt)

    seq = unpack_binop(node.body[0].value)

    assert len(seq) == 4

    assert isinstance(seq[0], ast.Name)
    assert seq[0].id == "a"

    assert isinstance(seq[1], ast.Constant)
    assert seq[1].value == "Hello"

    assert isinstance(seq[2], ast.Name)
    assert seq[2].id == "b"

    assert isinstance(seq[3], ast.Constant)
    assert seq[3].value == "World"


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
def test_transform():

    txt = """a + 'Hello' + b + 'World'"""
    expected = '''f"{a}Hello{b}World"'''

    new, changed = transform_concat(txt)

    assert changed
    assert new == expected
