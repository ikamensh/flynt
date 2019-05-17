from fstringify.transform import fstringify_code

def test_fmt_spec():
    code = '''a = "my string {:.2f}".format(var)'''
    expected = '''a = f"my string {var:.2f}"'''

    new, meta = fstringify_code(code)

    assert meta['changed']
    assert new == expected


def test_parenthesis():

    code = '''html_title = "Flask Documentation ({})".format(version)'''
    expected = '''html_title = f"Flask Documentation ({version})"'''

    new, meta = fstringify_code(code)

    assert meta['changed']
    assert new == expected


def test_numbered():

    code = '''html_title = "Flask Documentation ({0})".format(version)'''
    expected = '''html_title = f"Flask Documentation ({version})"'''

    new, meta = fstringify_code(code)

    assert meta['changed']
    assert new == expected


def test_mixed_numbered():
    code = '''html_title = "Flask Documentation ({1} {0:.2f} {name})".format(version,sprt,name=NAME)'''
    expected = '''html_title = f"Flask Documentation ({sprt} {version:.2f} {NAME})"'''

    new, meta = fstringify_code(code)

    assert meta['changed']
    assert new == expected

def test_unpacking_no_change():
    code = '''e.description = "KeyError: '{}'".format(*e.args)'''
    new, meta = fstringify_code(code)
    assert not meta['changed']
    assert new == code

def test_kw_unpacking_no_change():
    code = '''e.description = "KeyError: '{some_name}'".format(**kwargs)'''
    new, meta = fstringify_code(code)
    assert not meta['changed']
    assert new == code



