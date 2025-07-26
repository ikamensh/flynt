import ast

import pytest

from flynt.state import State
from flynt.transform.transform import transform_chunk


def transform_chunk_from_str(code: str, state):
    tree = ast.parse(code)
    return transform_chunk(tree, state)


def test_fmt_spec(state: State):
    code = """"my string {:.2f}".format(var)"""
    expected = '''f"""my string {var:.2f}"""'''

    new, changed = transform_chunk_from_str(code, state)

    assert changed
    assert new == expected


def test_expr_no_paren(state: State):
    code = """"my string {:.2f}".format(var+1)"""
    expected = '''f"""my string {var + 1:.2f}"""'''

    new, changed = transform_chunk_from_str(code, state)

    assert changed
    assert new == expected


def test_newline(state: State):
    code = r""""echo '{}'\n".format(self.FLUSH_CMD)"""
    expected = '''f"""echo '{self.FLUSH_CMD}'\\n"""'''

    new, changed = transform_chunk_from_str(code, state)

    assert changed
    assert new == expected


def test_parenthesis(state: State):
    code = """"Flask Documentation ({})".format(version)"""
    expected = '''f"""Flask Documentation ({version})"""'''

    new, changed = transform_chunk_from_str(code, state)

    assert changed
    assert new == expected


def test_implicit_string_concat(state: State):
    code = """"Helloo {}" "!!!".format(world)"""
    expected = '''f"""Helloo {world}!!!"""'''

    new, changed = transform_chunk_from_str(code, state)

    assert changed
    assert new == expected


def test_multiline(state: State):
    code = """
    "Flask Documentation ({})".format(
    version
)
    """.strip()
    expected = '''f"""Flask Documentation ({version})"""'''

    new, changed = transform_chunk_from_str(code, state)

    assert changed
    assert new == expected


def test_numbered(state: State):
    code = '''"""Flask Documentation ({0})""".format(version)'''
    expected = '''f"""Flask Documentation ({version})"""'''

    new, changed = transform_chunk_from_str(code, state)

    assert changed
    assert new == expected


def test_mixed_numbered(state: State):
    code = (
        """"Flask Documentation ({1} {0:.2f} {name})".format(version,sprt,name=NAME)"""
    )
    expected = '''f"""Flask Documentation ({sprt} {version:.2f} {NAME})"""'''

    new, changed = transform_chunk_from_str(code, state)

    assert changed
    assert new == expected


def test_unpacking_no_change(state: State):
    code = """e.description = "KeyError: '{}'".format(*e.args)"""
    new, changed = transform_chunk_from_str(code, state)
    assert not changed


def test_kw_unpacking_no_change(state: State):
    code = """e.description = "KeyError: '{some_name}'".format(**kwargs)"""
    new, changed = transform_chunk_from_str(code, state)
    assert not changed


def test_digit_grouping(state: State):
    code = """"Failed after {:,}".format(x)"""
    expected = '''f"""Failed after {x:,}"""'''

    new, changed = transform_chunk_from_str(code, state)

    assert changed
    assert new == expected


def test_digit_grouping_2(state: State):
    code = """
    "Search: finished in {0:,} ms.".format(vm.search_time_elapsed_ms)
    """.strip()
    expected = '''
    f"""Search: finished in {vm.search_time_elapsed_ms:,} ms."""
    '''.strip()

    new, changed = transform_chunk_from_str(code, state)

    assert changed
    assert new == expected


@pytest.mark.parametrize(
    "s",
    (
        # invalid format strings
        "'{'.format(a)",
        "'}'.format(a)",
        # starargs
        '"{} {}".format(*a)',
        '"{foo} {bar}".format(**b)',
        # likely makes the format longer
        '"{0} {0}".format(arg)',
        '"{x} {x}".format(arg)',
        '"{x.y} {x.z}".format(arg)',
        # bytestrings don't participate in `.format()` or `f''`
        # but are legal in python 2
        'b"{} {}".format(a, b)',
        # for now, too difficult to rewrite correctly
        '"{a[b]}".format(a=a)',
        '"{a.a[b]}".format(a=a)',
        # not enough placeholders / placeholders missing
        '"{}{}".format(a)',
        '"{a}{b}".format(a=a)',
        # too complex syntax
        '"{:{}}".format(x, y)',
        '"{}".format(b"\\n")',
        '"{}".format("\\n".join(items))',
        'msg = "{}\\nPossible solutions:\\n{}".format(msg, "\\n".join(solutions))',
        "return '{}({})'.format(node.__class__.__name__, ',\\n    '.join(values))",
        'self.assertEqual(len(expected), len(result), "Unmatched lines. Got:\\n{}\\nExpected:\\n{}".format("\\n".join(expected), "\\n".join(result)))',
        'self.assertEqual(len(result_lines), len(expected_lines), "Unmatched lines. Got:\\n{}\\nExpected:\\n{}".format("\\n".join(result_lines), expected))',
        "code.putln('\"{}.{}\",'.format(self.full_module_name, classname.replace('\"', '')))",
    ),
)
def test_fix_fstrings_noop(s, state: State):
    new, changed = transform_chunk_from_str(s, state)
    assert not changed


@pytest.mark.parametrize(
    ("s", "expected"),
    (
        ('"{} {}".format(a, b)', 'f"""{a} {b}"""'),
        ('"{1} {0}".format(a, b)', 'f"""{b} {a}"""'),
        ('"{x.y}".format(x=z)', 'f"""{z.y}"""'),
        ('"{0.y}".format(z)', 'f"""{z.y}"""'),
        ('"{.y}".format(z)', 'f"""{z.y}"""'),
        ('"{.x} {.y}".format(a, b)', 'f"""{a.x} {b.y}"""'),
        ('"{} {}".format(a.b, c.d)', 'f"""{a.b} {c.d}"""'),
        ('"hello {}!".format(name)', 'f"""hello {name}!"""'),
        ('"{}{{}}{}".format(escaped, y)', 'f"""{escaped}{{}}{y}"""'),
        ('"{}{b}{}".format(a, c, b=b)', 'f"""{a}{b}{c}"""'),
        # TODO: poor man's f-strings?
        # '"{foo}".format(**locals())'
        # TODO: re-evaluate edge cases ported over by #11
        # weird syntax
        ('"{}" . format(x)', 'f"""{x}"""'),
        # spans multiple lines
        ('"{}".format(\n    a,\n)', 'f"""{a}"""'),
    ),
)
def test_fix_fstrings(s, expected, state: State):
    new, changed = transform_chunk_from_str(s, state)
    assert changed
    assert new == expected


def test_disabled_transforms():
    # Test that disabling transforms does disable them
    assert not transform_chunk_from_str(
        '"my string {:.2f}".format(var)',
        state=State(transform_format=False),
    )[1]
    assert not transform_chunk_from_str(
        '"my string {:.2f}" % var',
        state=State(transform_percent=False),
    )[1]


def test_skip_variable_format(state: State):
    code = 'template = "Hello {0}"\nresult = template.format(name)'

    new, changed = transform_chunk_from_str(code, state)

    assert not changed
