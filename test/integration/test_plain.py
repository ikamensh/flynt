from flint.api import flint_str


def test_simple():
    txt_in = 'a = "my string {}".format(var)'
    expected_out = "a = f'my string {var}'\n"

    out, count = flint_str(txt_in)

    assert out == expected_out
    assert count == 1



def test_many_vars():
    txt_in = 'a = "my string {}, but also {} and {}".format(var, a, cada_bra)'
    expected_out = "a = f'my string {var}, but also {a} and {cada_bra}'\n"

    out, count = flint_str(txt_in)

    assert out == expected_out
    assert count == 1

def test_count():
    txt_in = 'a = "my string {}".format(var)\n' \
             'a = "my string {}".format(var)'

    out, count = flint_str(txt_in)
    assert count == 2

def test_var_name():
    txt_in = 'a = "my string {var_name}".format(var_name = var)'
    expected_out = "a = f'my string {var}'\n"

    out, count = flint_str(txt_in)

    assert out == expected_out
    assert count == 1



# def test_many_lines_one_fmt():
#
#     txt_in = 'a = "my string {}".format(var)'
#     expected_out = "a = f'my string {var}'\n"
#
#     assert flint_str(txt_in) == expected_out