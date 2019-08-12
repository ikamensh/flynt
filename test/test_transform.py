from flynt.transform import transform_chunk
import pytest

def test_fmt_spec():
    code = '''"my string {:.2f}".format(var)'''
    expected = '''f"""my string {var:.2f}"""'''

    new, meta = transform_chunk(code)

    assert meta['changed']
    assert new == expected

@pytest.mark.xfail(reason="problem in dependency - astor https://github.com/berkerpeksag/astor/issues/153")
def test_expr_no_paren():
    code = '''"my string {:.2f}".format(var+1)'''
    expected = '''f"""my string {var + 1:.2f}"""'''

    new, meta = transform_chunk(code)

    assert meta['changed']
    assert new == expected

def test_newline():
    code = r'''"echo '{}'\n".format(self.FLUSH_CMD)'''
    expected = '''f"""echo '{self.FLUSH_CMD}'\\n"""'''

    new, meta = transform_chunk(code)

    assert meta['changed']
    assert new == expected


def test_parenthesis():

    code = '''"Flask Documentation ({})".format(version)'''
    expected = '''f"""Flask Documentation ({version})"""'''

    new, meta = transform_chunk(code)

    assert meta['changed']
    assert new == expected




def test_implicit_string_concat():

    code = '''"Helloo {}" "!!!".format(world)'''
    expected = '''f"""Helloo {world}!!!"""'''

    new, meta = transform_chunk(code)

    assert meta['changed']
    assert new == expected

def test_multiline():

    code = '''
    "Flask Documentation ({})".format(
    version
)
    '''.strip()
    expected = '''f"""Flask Documentation ({version})"""'''

    new, meta = transform_chunk(code)

    assert meta['changed']
    assert new == expected


def test_numbered():

    code = '''"""Flask Documentation ({0})""".format(version)'''
    expected = '''f"""Flask Documentation ({version})"""'''

    new, meta = transform_chunk(code)

    assert meta['changed']
    assert new == expected


def test_mixed_numbered():
    code = '''"Flask Documentation ({1} {0:.2f} {name})".format(version,sprt,name=NAME)'''
    expected = '''f"""Flask Documentation ({sprt} {version:.2f} {NAME})"""'''

    new, meta = transform_chunk(code)

    assert meta['changed']
    assert new == expected

def test_unpacking_no_change():
    code = '''e.description = "KeyError: '{}'".format(*e.args)'''
    new, meta = transform_chunk(code)
    assert not meta['changed']
    assert new == code

def test_kw_unpacking_no_change():
    code = '''e.description = "KeyError: '{some_name}'".format(**kwargs)'''
    new, meta = transform_chunk(code)
    assert not meta['changed']
    assert new == code

def test_digit_grouping():
    code = '''"Failed after {:,}".format(x)'''
    expected = '''f"""Failed after {x:,}"""'''

    new, meta = transform_chunk(code)

    assert meta['changed']
    assert new == expected


def test_digit_grouping_2():
    code = '''
    "Search: finished in {0:,} ms.".format(vm.search_time_elapsed_ms)
    '''.strip()
    expected = '''
    f"""Search: finished in {vm.search_time_elapsed_ms:,} ms."""
    '''.strip()

    new, meta = transform_chunk(code)

    assert meta['changed']
    assert new == expected


@pytest.mark.parametrize(
    's',
    (
        # syntax error
        '(',
        # invalid format strings
        "'{'.format(a)", "'}'.format(a)",
        # starargs
        '"{} {}".format(*a)', '"{foo} {bar}".format(**b)"',
        # likely makes the format longer
        '"{0} {0}".format(arg)', '"{x} {x}".format(arg)',
        '"{x.y} {x.z}".format(arg)',
        # bytestrings don't participate in `.format()` or `f''`
        # but are legal in python 2
        'b"{} {}".format(a, b)',
        # for now, too difficult to rewrite correctly
        '"{a[b]}".format(a=a)',
        '"{a.a[b]}".format(a=a)',
        # not enough placeholders / placeholders missing
        '"{}{}".format(a)', '"{a}{b}".format(a=a)',
    ),
)
def test_fix_fstrings_noop(s):
    new, meta = transform_chunk(s)
    assert not meta['changed']
    assert new == s


@pytest.mark.parametrize(
    ('s', 'expected'),
    (
        ('"{} {}".format(a, b)', 'f"""{a} {b}"""'),
        ('"{1} {0}".format(a, b)', 'f"""{b} {a}"""'),
        pytest.param('"{x.y}".format(x=z)', 'f"""{z.y}"""', marks=pytest.mark.xfail(reason='Possible not correct bevaviour')),
        pytest.param('"{.x} {.y}".format(a, b)', 'f"""{a.x} {b.y}"""', marks=pytest.mark.xfail(reason='Possible not correct bevaviour')),
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
        pytest.param('"{:{}}".format(x, y)', 'f"""{x:{{y}}}"""', marks=pytest.mark.xfail(reason='Possible not correct bevaviour')),
    ),
)
def test_fix_fstrings(s, expected):
    new, meta = transform_chunk(s)
    assert meta['changed']
    assert new == expected

