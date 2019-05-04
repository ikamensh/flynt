from flint.launch import flint_str


def test_simple():
    txt_in = 'a = "my string {}".format(var)'
    expected_out = "a = f'my string {var}'\n"

    assert flint_str(txt_in) == expected_out



def test_many_vars():
    txt_in = 'a = "my string {}, but also {} and {}".format(var, a, cada_bra)'
    expected_out = "a = f'my string {var}, but also {a} and {cada_bra}'\n"

    assert flint_str(txt_in) == expected_out