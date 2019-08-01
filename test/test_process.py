import pytest

from flynt import process

def test_one_string():
    s_in = """a = 'my string {}, but also {} and {}'.format(var, f, cada_bra)"""
    s_expected = """a = f'my string {var}, but also {f} and {cada_bra}'"""

    s_out, count = process.fstringify_code_by_line(s_in)
    assert s_out == s_expected


def test_multiline():
    s_in = """a = 'my string {}, but also {} and {}'.format(\nvar, \nf, \ncada_bra)"""
    s_expected = """a = f'my string {var}, but also {f} and {cada_bra}'"""

    s_out, count = process.fstringify_code_by_line(s_in)
    assert s_out == s_expected

def test_conversion():
    s_in = """a = 'my string {}, but also {!r} and {!a}'.format(var, f, cada_bra)"""
    s_expected = """a = f'my string {var}, but also {f!r} and {cada_bra!a}'"""

    s_out, count = process.fstringify_code_by_line(s_in)
    assert s_out == s_expected


def test_invalid_conversion():
    s_in = """a = 'my string {}, but also {!b} and {!a}'.format(var, f, cada_bra)"""
    s_expected = s_in

    s_out, count = process.fstringify_code_by_line(s_in)
    assert s_out == s_expected

def test_invalid_conversion_names():
    s_in = """a = 'my string {var}, but also {f!b} and {cada_bra!a}'.format(var, f, cada_bra)"""
    s_expected = s_in

    s_out, count = process.fstringify_code_by_line(s_in)
    assert s_out == s_expected

    
def test_percent_newline():
    s_in = """a = '%s\\n' % var"""
    s_expected = """a = f'{var}\\n'"""

    s_out, count = process.fstringify_code_by_line(s_in)
    print(s_out)
    print(s_expected)
    assert s_out == s_expected

def test_format_newline():
    s_in = """a = '{}\\n'.format(var)"""
    s_expected = """a = f'{var}\\n'"""

    s_out, count = process.fstringify_code_by_line(s_in)
    assert s_out == s_expected


def test_format_tab():
    s_in = """a = '{}\\t'.format(var)"""
    s_expected = """a = f'{var}\\t'"""

    s_out, count = process.fstringify_code_by_line(s_in)
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



def test_openpyxl():
    s_in = """sheet['B{}'.format(i) : 'E{}'.format(i)]"""
    s_expected = """sheet[f'B{i}' : f'E{i}']"""
    s_out, count = process.fstringify_code_by_line(s_in)

    assert count == 2
    assert s_out == s_expected


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
    s_expected = """{'r': f'{row_idx:d}'}"""

    assert process.fstringify_code_by_line(s_in)[0] == s_expected


def test_legacy_unicode():
    s_in = """u'%s, Cadabra' % datetime.now().year"""
    s_expected = """f'{datetime.now().year}, Cadabra'"""

    assert process.fstringify_code_by_line(s_in)[0] == s_expected

def test_double_percent_no_prob():
    s_in = "{'r': '%%%s%%' % row_idx}"
    s_expected = "{'r': '%%%s%%' % row_idx}"

    assert process.fstringify_code_by_line(s_in)[0] == s_expected


def test_percent_attr():
    s_in = """src_info = 'application "%s"' % srcobj.import_name"""
    s_expected = """src_info = f'application "{srcobj.import_name}"'"""

    out, count = process.fstringify_code_by_line(s_in)
    assert out == s_expected


def test_legacy_fmtspec():
    s_in = """d = '%i' % var"""
    s_expected = """d = f'{var:d}'"""

    out, count = process.fstringify_code_by_line(s_in)
    assert out == s_expected


def test_decimal_precision():
    s_in = """e = '%.03f' % var"""
    s_expected = """e = f'{var:.03f}'"""

    out, count = process.fstringify_code_by_line(s_in)
    assert out == s_expected

def test_width_spec():
    s_in = "{'r': '%03d' % row_idx}"
    s_expected = """{'r': f'{row_idx:03d}'}"""

    assert process.fstringify_code_by_line(s_in)[0] == s_expected

def test_equiv_expressions_repr():
    name = 'bla'

    s_in = """'Setting %20r must be uppercase.' % name"""

    out, count = process.fstringify_code_by_line(s_in)
    assert eval(out) == eval(s_in)


def test_equiv_expressions_s():
    name = 'bla'

    s_in = """'Setting %20s must be uppercase.' % name"""

    out, count = process.fstringify_code_by_line(s_in)
    assert eval(out) == eval(s_in)

@pytest.mark.parametrize('fmt_spec', 'egdixXu')
@pytest.mark.parametrize('number', [0, 11, 0b111])
def test_integers_equivalence(number, fmt_spec):
    percent_fmt_string = f"""'Setting %{fmt_spec} must be uppercase.' % number"""
    out, count = process.fstringify_code_by_line(percent_fmt_string)

    assert eval(out) == eval(percent_fmt_string)

@pytest.mark.parametrize('fmt_spec', 'egf')
@pytest.mark.parametrize('number', [3.33333333, 15e-44, 3.142854])
def test_floats_equivalence(number, fmt_spec):
    percent_fmt_string = f"""'Setting %{fmt_spec} must be uppercase.' % number"""
    out, count = process.fstringify_code_by_line(percent_fmt_string)

    assert eval(out) == eval(percent_fmt_string)


@pytest.mark.parametrize('fmt_spec', ['.02f', '.01e', '.04g', '05f'])
@pytest.mark.parametrize('number', [3.33333333, 15e-44, 3.142854])
def test_floats_precision_equiv(number, fmt_spec):
    percent_fmt_string = f"""'Setting %{fmt_spec} must be uppercase.' % number"""
    out, count = process.fstringify_code_by_line(percent_fmt_string)

    assert eval(out) == eval(percent_fmt_string)


