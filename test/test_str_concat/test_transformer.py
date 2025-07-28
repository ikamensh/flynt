import ast


from flynt.state import State
from flynt.string_concat.transformer import transform_concat, unpack_binop


def transform_concat_from_str(code: str, state=State()):
    tree = ast.parse(code)
    return transform_concat(tree, state)


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


def test_transform():
    txt = """a + 'Hello' + b + 'World'"""
    expected = '''f"{a}Hello{b}World"'''

    new, changed = transform_concat_from_str(txt)

    assert changed
    assert new == expected


def test_transform_nonatomic():
    txt = """'blah' + (thing - 1)"""
    expected = '''f"blah{thing - 1}"'''

    new, changed = transform_concat_from_str(txt)

    assert changed
    assert new == expected


def test_transform_attribute():
    txt = """'blah' + blah.blah"""
    expected = '''f"blah{blah.blah}"'''

    new, changed = transform_concat_from_str(txt)

    assert changed
    assert new == expected


def test_transform_complex():
    txt = """'blah' + lst[123].process(x, y, z) + 'Yeah'"""
    expected = '''f"blah{lst[123].process(x, y, z)}Yeah"'''

    new, changed = transform_concat_from_str(txt)

    assert changed
    assert new == expected


def test_string_in_string():
    txt = """'blah' + blah.blah('more' + vars)"""
    expected = '''f"blah{blah.blah(f'more{vars}')}"'''

    new, changed = transform_concat_from_str(txt)

    assert changed
    assert new == expected


def test_concats_fstring():
    txt = """print(f'blah{thing}' + 'blah' + otherThing + f"is {x:d}")"""
    expected = """print(f'blah{thing}blah{otherThing}is {x:d}')"""

    new, changed = transform_concat_from_str(txt)

    assert changed
    assert new == expected


def test_string_in_string_x3():
    txt = """'blah' + blah.blah('more' + vars.foo('other' + b))"""

    new, changed = transform_concat_from_str(txt)

    assert changed
    assert "'blah' +" in new


def test_existing_fstr():
    txt = """f'blah{thing}' + otherThing + 'blah'"""
    expected = '''f"blah{thing}{otherThing}blah"'''

    new, changed = transform_concat_from_str(txt)

    assert changed
    assert new == expected


def test_existing_fstr_expr():
    txt = """f'blah{thing}' + otherThing + f'blah{thing + 1}'"""
    expected = '''f"blah{thing}{otherThing}blah{thing + 1}"'''

    new, changed = transform_concat_from_str(txt)

    assert changed
    assert new == expected


def test_embedded_fstr():
    txt = """print(f"{f'blah{var}' + abc}blah")"""
    expected = """print(f'blah{var}{abc}blah')"""

    new, changed = transform_concat_from_str(txt)

    assert changed
    assert new == expected


def test_backslash():
    txt = """blah1 \
        + 'b'"""

    expected = '''f"{blah1}b"'''
    new, changed = transform_concat_from_str(txt)

    assert changed
    assert new == expected


def test_parens():
    txt = """(blah1
        + 'b')"""

    expected = '''f"{blah1}b"'''
    new, changed = transform_concat_from_str(txt)

    assert changed
    assert new == expected


def test_concat_only_literals():
    txt = '"here" + r"\\there"'
    expected = '"here\\\\there"'
    new, changed = transform_concat_from_str(txt)

    assert changed
    assert new == expected


noexc_in = """individual_tests = [re.sub(r"\.py$", "", test) + ".py" for test in tests if not test.endswith('*')]"""
noexc_out = """individual_tests = [f"{re.sub(r"\.py$", "", test)}.py" for test in tests if not test.endswith('*')]"""


def test_noexc():
    new, changed = transform_concat_from_str(noexc_in)
    assert not changed
    assert new == ""
