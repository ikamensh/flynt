from fstringify import process

def test_one_string():
    s_in = """a = 'my string {}, but also {} and {}'.format(var, f, cada_bra)"""
    s_expected = """a = f'my string {var}, but also {f} and {cada_bra}'"""

    s_out, count = process.fstringify_code_by_line(s_in)
    print(s_out)
    print(s_expected)
    assert s_out == s_expected


indented = """
var = 5
if var % 3 == 0:
    a = "my string {}".format(var)""".strip()

def test_indented():
    s_expected = '''    a = f"my string {var}"'''
    s_out, count = process.fstringify_code_by_line(indented)

    assert count == 1
    assert s_out.split('\n')[2] == s_expected

code_empty_line = """
def write_row(self, xf, row, row_idx):

    attrs = {'r': '{}'.format(row_idx)}""".strip()

def test_empty_line():
    s_expected = '''    attrs = {'r': f'{row_idx}'}'''
    s_out, count = process.fstringify_code_by_line(code_empty_line)

    assert count == 1
    assert s_out.split('\n')[2] == s_expected

def test_dict_perc():
    s_in = "{'r': '%d' % row_idx}"
    s_expected = """{'r': f'{row_idx}'}"""

    assert process.fstringify_code_by_line(s_in)[0] == s_expected


def test_percent_attr():
    s_in = """src_info = 'application "%s"' % srcobj.import_name"""
    s_expected = """src_info = f'application "{srcobj.import_name}"'"""

    out, count = process.fstringify_code_by_line(s_in)
    print(out, s_expected)
    assert out == s_expected
