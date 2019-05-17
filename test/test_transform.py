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


