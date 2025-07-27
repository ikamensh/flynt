import sys

import pytest

from flynt import code_editor
from flynt.state import State


def test_timestamp(state: State):
    s_in = """'Timestamp: {:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now())"""
    s_expected = """f'Timestamp: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_ifexpr(state: State):
    s_in = """'%s' % (a if c else b)"""
    s_expected = """f'{a if c else b}'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_binop(state: State):
    s_in = """'%s' % (a+b+c)"""
    s_expected = """f'{a + b + c}'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_call(state: State):
    s_in = """'%s' % fn(var)"""
    s_expected = """f'{fn(var)}'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_string_specific_len_right_aligned(state: State):
    s_in = """'%5s' % CLASS_NAMES[labels[j]]"""
    s_expected = """f'{CLASS_NAMES[labels[j]]:>5}'"""

    state.aggressive = 1
    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_string_specific_len_left_aligned(state: State):
    s_in = """'%-5s' % CLASS_NAMES[labels[j]]"""
    s_expected = """f'{CLASS_NAMES[labels[j]]:5}'"""

    state.aggressive = 1
    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_dont_wrap_int(state: State):
    s_in = """print('Int cast %d' % int(18.81))"""
    s_expected = """print(f'Int cast {int(18.81)}')"""

    state.aggressive = 1
    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_dont_wrap_len(state: State):
    s_in = """print('List length %d' % len(sys.argv))"""
    s_expected = """print(f'List length {len(sys.argv)}')"""

    state.aggressive = 1
    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_string_in_string_single(state: State):
    s_in = """print('getlivejpg: %s: %s' % (camera['name'], errmsg))"""
    s_expected = """print(f"getlivejpg: {camera['name']}: {errmsg}")"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_percent_tuple(state: State):
    s_in = """print("%s %s " % (var+var, abc))"""
    s_expected = """print(f"{var + var} {abc} ")"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_percent_list(state: State):
    s_in = """print("%s %s " % [var+var, abc])"""
    s_expected = """print(f"{var + var} {abc} ")"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_percent_str_call(state: State):
    s_in = """'%s %s' % (str(var), uno)"""
    s_expected = """f'{var!s} {uno}'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_percent_repr_call(state: State):
    s_in = """'%s' % repr(var)"""
    s_expected = """f'{var!r}'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_part_of_concat(state: State):
    s_in = """print('blah{}'.format(thing) + 'blah' + otherThing + "is %f" % x)"""
    s_expected = """print(f'blah{thing}' + 'blah' + otherThing + f"is {x:f}")"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_one_string(state: State):
    s_in = """a = 'my string {}, but also {} and {}'.format(var, f, cada_bra)"""
    s_expected = """a = f'my string {var}, but also {f} and {cada_bra}'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_nonatomic(state: State):
    s_in = """'blah{0}'.format(thing - 1)"""
    s_expected = """f'blah{thing - 1}'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_format_str_call(state: State):
    s_in = """'{}'.format(str(var))"""
    s_expected = """f'{var!s}'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_format_repr_call(state: State):
    s_in = """'{}'.format(repr(var))"""
    s_expected = """f'{var!r}'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_noqa(state: State):
    s_in = """a = 'my string {}, but also {} and {}'.format(var, f, cada_bra)  # noqa: flynt"""
    s_expected = """a = 'my string {}, but also {} and {}'.format(var, f, cada_bra)  # noqa: flynt"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_noqa_other(state: State):
    s_in = """a = '%s\\n' % var  # noqa: W731, flynt"""
    s_expected = """a = '%s\\n' % var  # noqa: W731, flynt"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_flynt_skip(state: State):
    s_in = """a = 'my string {}, but also {} and {}'.format(var, f, cada_bra)  # flynt: skip"""
    s_expected = """a = 'my string {}, but also {} and {}'.format(var, f, cada_bra)  # flynt: skip"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_multiline(state: State):
    s_in = """a = 'my string {}, but also {} and {}'.format(\nvar, \nf, \ncada_bra)"""
    s_expected = """a = f'my string {var}, but also {f} and {cada_bra}'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_conversion(state: State):
    s_in = """a = 'my string {}, but also {!r} and {!a}'.format(var, f, cada_bra)"""
    s_expected = """a = f'my string {var}, but also {f!r} and {cada_bra!a}'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_invalid_conversion(state: State):
    s_in = """a = 'my string {}, but also {!b} and {!a}'.format(var, f, cada_bra)"""
    s_expected = s_in

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_invalid_conversion_names(state: State):
    s_in = """a = 'but also {f!b} and {cada_bra!a}'.format(f, cada_bra)"""
    s_expected = s_in

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_dangerous_tuple(state: State):
    s_in = """print("%5.0f   %12.6g %12.6g %s" % (fmin_data + (step,)))"""
    s_expected = s_in

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_percent_newline(state: State):
    s_in = """a = '%s\\n' % var"""
    s_expected = """a = f'{var}\\n'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    print(s_out)
    print(s_expected)
    assert s_out == s_expected


def test_format_newline(state: State):
    s_in = """a = '{}\\n'.format(var)"""
    s_expected = """a = f'{var}\\n'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


def test_format_tab(state: State):
    s_in = """a = '{}\\t'.format(var)"""
    s_expected = """a = f'{var}\\t'"""

    s_out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert s_out == s_expected


indented = """
var = 5
if var % 3 == 0:
    a = "my string {}".format(var)""".strip()


def test_indented(state: State):
    s_expected = '''    a = f"my string {var}"'''
    s_out, count = code_editor.fstringify_code_by_line(indented, state)

    assert count == 1
    assert s_out.split("\n")[2] == s_expected


split = """
var = {}
a = 'foo {}'.format(
    var.get('bar'))
"""

split_expected = """
var = {}
a = f"foo {var.get('bar')}"
"""


def test_line_split(state: State):
    s_out, count = code_editor.fstringify_code_by_line(split, state)

    assert count == 1
    assert s_out == split_expected


def test_line_split_single_line(state: State):
    s_in = """a = 'foo {}'.format(var.get('bar'))"""
    expected = """a = f"foo {var.get('bar')}\""""
    s_out, count = code_editor.fstringify_code_by_line(s_in, state)

    assert count == 1
    assert s_out == expected


split_kw = """
var = {}
a = 'foo {key}'.format(
    key=var.get('bar'))
"""

split_expected_kw = """
var = {}
a = f"foo {var.get('bar')}"
"""


def test_line_split_kw(state: State):
    s_out, count = code_editor.fstringify_code_by_line(split_kw, state)

    assert count == 1
    assert s_out == split_expected_kw


def test_openpyxl(state: State):
    s_in = """sheet['B{}'.format(i) : 'E{}'.format(i)]"""
    s_expected = """sheet[f'B{i}' : f'E{i}']"""
    s_out, count = code_editor.fstringify_code_by_line(s_in, state)

    assert count == 2
    assert s_out == s_expected


def test_double_percent_2(state: State):
    s_in = """print("p = %.3f%%" % (100 * p))"""
    s_expected = """print(f"p = {100 * p:.3f}%")"""
    s_out, count = code_editor.fstringify_code_by_line(s_in, state)

    assert count == 1
    assert s_out == s_expected


def test_str_in_str(state: State):
    s_in = """a = "beautiful numbers to follow: {}".format(" ".join(lst))"""
    s_expected = """a = f"beautiful numbers to follow: {' '.join(lst)}\""""
    s_out, count = code_editor.fstringify_code_by_line(s_in, state)

    assert count == 1
    assert s_out == s_expected


def test_str_in_str_single_quote(state: State):
    s_in = """a = 'beautiful numbers to follow: {}'.format(" ".join(lst))"""
    s_expected = """a = f"beautiful numbers to follow: {' '.join(lst)}\""""
    s_out, count = code_editor.fstringify_code_by_line(s_in, state)

    assert count == 1
    assert s_out == s_expected


def test_chain_fmt(state: State):
    s_in = """a = "Hello {}".format(d["a{}".format(key)])"""
    s_expected = """a = f"Hello {d[f'a{key}']}\""""
    s_out, count = code_editor.fstringify_code_by_line(s_in, state)

    assert count == 1
    assert s_out == s_expected


def test_chain_fmt_3(state: State):
    s_in = """a = "Hello {}".format(d["a{}".format( d["a{}".format(key) ]) ] )"""
    s_out, count = code_editor.fstringify_code_by_line(s_in, state)

    assert count == 0


code_empty_line = """
def write_row(self, xf, row, row_idx):

    attrs = {'r': '{}'.format(row_idx)}""".strip()


def test_empty_line(state: State):
    s_expected = """    attrs = {'r': f'{row_idx}'}"""
    s_out, count = code_editor.fstringify_code_by_line(code_empty_line, state)

    assert count == 1
    assert s_out.split("\n")[2] == s_expected


def test_dict_perc(state: State):
    s_in = "{'r': '%s' % row_idx}"
    s_expected = """{'r': f'{row_idx}'}"""

    assert code_editor.fstringify_code_by_line(s_in, state)[0] == s_expected


def test_legacy_unicode(state: State):
    s_in = """u'%s, Cadabra' % datetime.now().year"""
    s_expected = """f'{datetime.now().year}, Cadabra'"""

    assert code_editor.fstringify_code_by_line(s_in, state)[0] == s_expected


def test_double_percent_no_prob(state: State):
    s_in = "{'r': '%%%s%%' % row_idx}"
    s_expected = "{'r': f'%{row_idx}%'}"

    assert code_editor.fstringify_code_by_line(s_in, state)[0] == s_expected


def test_percent_dict(state: State):
    s_in = """a = '%(?)s world' % {'?': var}"""
    s_expected = """a = f'{var} world'"""

    assert code_editor.fstringify_code_by_line(s_in, state)[0] == s_expected


def test_percent_dict_fmt(state: State):
    s_in = """a = '%(?)ld world' % {'?': var}"""
    s_expected = """a = f'{int(var)} world'"""
    state.aggressive = 1
    assert code_editor.fstringify_code_by_line(s_in, state)[0] == s_expected


def test_percent_dict_fmt_extra_aggressive(state: State):
    s_in = """a = '%(?)ld world' % {'?': var}"""
    s_expected = """a = f'{var} world'"""
    state.aggressive = 2
    assert code_editor.fstringify_code_by_line(s_in, state)[0] == s_expected


def test_double_percent_dict(state: State):
    s_in = """a = '%(?)s%%' % {'?': var}"""
    s_expected = """a = f'{var}%'"""

    assert code_editor.fstringify_code_by_line(s_in, state)[0] == s_expected


percent_dict_reused_key = """a = '%(?)s %(?)s' % {'?': var}"""


def test_percent_dict_reused_key_noop(state: State):
    assert (
        code_editor.fstringify_code_by_line(percent_dict_reused_key, state)[0]
        == percent_dict_reused_key
    )


def test_percent_dict_reused_key_aggressive(state: State):
    s_expected = """a = f'{var} {var}'"""

    state.aggressive = 1
    assert (
        code_editor.fstringify_code_by_line(percent_dict_reused_key, state)[0]
        == s_expected
    )


def test_percent_dict_name(state: State):
    s_in = """a = '%(?)s world' % var"""
    s_expected = """a = f"{var['?']} world\""""

    assert code_editor.fstringify_code_by_line(s_in, state)[0] == s_expected


def test_percent_dict_names(state: State):
    s_in = """a = '%(?)s %(world)s' % var"""
    s_expected = """a = f"{var['?']} {var['world']}\""""

    assert code_editor.fstringify_code_by_line(s_in, state)[0] == s_expected


def test_percent_attr(state: State):
    s_in = """src_info = 'application "%s"' % srcobj.import_name"""
    s_expected = """src_info = f'application "{srcobj.import_name}"'"""

    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert out == s_expected


def test_percent_dict_prefix(state: State):
    s_in = """a = '%(?)s %(world).2f' % var"""
    s_expected = """a = f"{var['?']} {var['world']:.2f}\""""

    assert code_editor.fstringify_code_by_line(s_in, state)[0] == s_expected


def test_legacy_fmtspec(state: State):
    s_in = """d = '%i' % var"""
    s_expected = """d = f'{int(var)}'"""

    state.aggressive = 1
    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert out == s_expected


def test_legacy_fmtspec_extra_aggressive(state: State):
    s_in = """d = '%i' % var"""
    s_expected = """d = f'{var}'"""

    state.aggressive = 2
    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert out == s_expected


def test_str_in_str_curly(state: State):
    s_in = """desired_info += ["'clusters_options' items: {}. ".format({'random_option'})]"""

    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert count == 0


def test_str_in_str_methods(state: State):
    s_in = r"""string += '{} = {}\n'.format(('.').join(listKeys), json.JSONEncoder().encode(val))"""
    s_out = (
        """string += f"{'.'.join(listKeys)} = {json.JSONEncoder().encode(val)}\\n\""""
    )

    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert out == s_out
    assert count > 0


def test_decimal_precision(state: State):
    s_in = """e = '%.03f' % var"""
    s_expected = """e = f'{var:.03f}'"""

    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert out == s_expected


def test_width_spec(state: State):
    s_in = "{'r': '%03f' % row_idx}"
    s_expected = """{'r': f'{row_idx:03f}'}"""

    state.aggressive = 1
    assert code_editor.fstringify_code_by_line(s_in, state)[0] == s_expected


def test_equiv_expressions_repr(state: State):
    name = "bla"  # noqa: F841

    s_in = """'Setting %20r must be uppercase.' % name"""

    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert eval(out) == eval(s_in)


def test_equiv_expressions_hex(state: State):
    a = 17  # noqa: F841

    s_in = """'%.3x' % a"""

    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert eval(out) == eval(s_in)


def test_equiv_expressions_s(state: State):
    name = "bla"  # noqa: F841

    s_in = """'Setting %20s must be uppercase.' % name"""

    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert eval(out) == eval(s_in)


@pytest.mark.skipif(sys.version_info < (3, 9), reason="requires python3.9 or higher")
def test_concat(state: State):
    s_in = """msg = a + " World\""""
    s_expected = """msg = f\"{a} World\""""

    s_out, count = code_editor.fstringify_concats(s_in, state)
    assert s_out == s_expected


@pytest.mark.skipif(sys.version_info < (3, 9), reason="requires python3.9 or higher")
def test_concat_two_sides(state: State):
    s_in = """t = 'T is a string of value: ' + val + ' and thats great!'"""
    s_expected = """t = f\"T is a string of value: {val} and thats great!\""""

    s_out, count = code_editor.fstringify_concats(s_in, state)
    assert s_out == s_expected


@pytest.mark.parametrize("fmt_spec", "egdixXu")
@pytest.mark.parametrize("number", [0, 11, 0b111])
def test_integers_equivalence(number, fmt_spec, state: State):
    percent_fmt_string = f"""'Setting %{fmt_spec} must be uppercase.' % number"""
    out, count = code_editor.fstringify_code_by_line(percent_fmt_string, state)

    assert eval(out) == eval(percent_fmt_string)


@pytest.mark.parametrize("fmt_spec", "egf")
@pytest.mark.parametrize("number", [3.333_333_33, 15e-44, 3.142_854])
def test_floats_equivalence(number, fmt_spec, state):
    percent_fmt_string = f"""'Setting %{fmt_spec} must be uppercase.' % number"""
    out, count = code_editor.fstringify_code_by_line(percent_fmt_string, state)

    assert eval(out) == eval(percent_fmt_string)


@pytest.mark.parametrize("fmt_spec", [".02f", ".01e", ".04g", "05f"])
@pytest.mark.parametrize("number", [3.333_333_33, 15e-44, 3.142_854])
def test_floats_precision_equiv(number, fmt_spec, state):
    percent_fmt_string = f"""'Setting %{fmt_spec} must be uppercase.' % number"""
    out, count = code_editor.fstringify_code_by_line(percent_fmt_string, state)

    assert eval(out) == eval(percent_fmt_string)


def test_multiline_tuple(state: State):
    s_in = """s = '%s' % (
                    v['key'])"""

    expected = """s = f"{v['key']}\""""

    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert out == expected


def test_kv_loop(state: State):
    s_in = """', '.join('{}={}'.format(k, v) for k, v in d)"""
    expected = """', '.join(f'{k}={v}' for k, v in d)"""

    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert out == expected


def test_unknown_mod_percend_dictionary(state: State):
    """Unknown modifier must not result in partial conversion!"""

    s_in = """\"%(a)-6d %(a)s" % d"""

    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert out == s_in


s_in_mixed_quotes = """'one is {} '"and two is {}".format(one, two)"""


def test_mixed_quote_types(state: State):
    """Test that a multiline, mixed-quotes expression is transformed."""

    expected = """f'one is {one} and two is {two}'"""

    out, count = code_editor.fstringify_code_by_line(s_in_mixed_quotes, state)
    assert out == expected


s_in_mixed_quotes_unsafe = """'one "{}" '", two {}".format('"'.join(one), two)"""


def test_mixed_quote_types_unsafe(state: State):
    """Transforming an expression with quotes in it is more tricky.

    Currently it's not transformed at all."""

    out, count = code_editor.fstringify_code_by_line(s_in_mixed_quotes_unsafe, state)
    assert out == s_in_mixed_quotes_unsafe


def test_super_call(state: State):
    """Regression for https://github.com/ikamensh/flynt/issues/103 -"""

    s_in = '"{}/{}".format(super(SuggestEndpoint, self).path, self.facet.suggest)'
    expected = 'f"{super(SuggestEndpoint, self).path}/{self.facet.suggest}"'

    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert count == 1
    assert out == expected


escaped = """
var = 'baz''foo " %s \\' bar' % var
"""

expected_escaped = """
var = f'bazfoo " {var} \\' bar'
"""


def test_escaped_mix(state: State):
    """Regression for https://github.com/ikamensh/flynt/issues/114"""

    out, count = code_editor.fstringify_code_by_line(escaped, state)
    assert count == 1
    assert out == expected_escaped


escaped_2 = """
var = 'baz'"foo ' %s \\" bar" % var
"""

expected_escaped_2 = """
var = f'bazfoo \\' {var} " bar'
"""


def test_escaped_mix_double(state: State):
    """Regression for https://github.com/ikamensh/flynt/issues/114"""

    out, count = code_editor.fstringify_code_by_line(escaped_2, state)
    assert count == 1
    assert out == expected_escaped_2


issue_112 = """
'some {} here as {}'.format(
text, placeholder)
"""

expected_112 = """
f'some {text} here as {placeholder}'
"""


def test_112(state: State):
    """Test for issue #112 on github"""
    out, count = code_editor.fstringify_code_by_line(issue_112, state)
    assert count == 1
    assert out == expected_112


issue_112_simple = """
'my string {}'.format(
    my_var,
)
"""

expected_112_simple = """
f'my string {my_var}'
"""


def test_112_simple(state: State):
    """Test for issue #112 on github with a different input."""
    out, count = code_editor.fstringify_code_by_line(issue_112_simple, state)
    assert count == 1
    assert out == expected_112_simple


def test_110(state: State):
    """Test for issue #110 on github"""
    s_in = "'{conn.login}:{conn.password}@'.format(conn=x)"
    expected_out = "f'{x.login}:{x.password}@'"
    state.aggressive = 1
    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert count == 1
    assert out == expected_out


def test_110_nonaggr(state: State):
    """Test for issue #110 on github - no change in code expected outside of -aggr flag"""
    s_in = "'{conn.login}:{conn.password}@'.format(conn=x)"
    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert count == 0


def test_literal_direct(state: State):
    s_in = """s = "%s/%s/%s" % (x, "two", y)"""
    expected_out = 's = f"{x}/two/{y}"'
    out, count = code_editor.fstringify_code_by_line(s_in, state)
    assert count == 1
    assert out == expected_out


def test_joins():
    s_in = """';'.join(['a', 'b', 'c'])"""
    expected_out = '"a;b;c"'
    out, count = code_editor.fstringify_static_joins(s_in, State())
    assert count > 0
    assert out == expected_out


def test_joins_octal_escape():
    s_in = """'\\40'.join(['a', 'b'])"""
    expected_out = '"a\\40b"'
    out, count = code_editor.fstringify_static_joins(s_in, State())
    assert count > 0
    assert out == expected_out
