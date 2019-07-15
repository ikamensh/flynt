from flynt.transform import transform_chunk

def test_fmt_spec():
    code = '''"my string {:.2f}".format(var)'''
    expected = '''f"""my string {var:.2f}"""'''

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

