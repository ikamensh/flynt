from fstringify.transform import fstringify_code

def test_fmt_spec():
    code = '''a = "my string {:.2f}".format(var)'''
    expected = '''a = f"my string {var:.2f}"'''

    new, meta = fstringify_code(code)

    assert meta['changed']
    assert new == expected
