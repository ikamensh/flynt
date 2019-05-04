from flint.launch import flint_str
from util import flint_test

# def test_twoliner(two_liner_content, two_liner_expected_output, output_file):
#     processed = flint_str(two_liner_content)
#     output_file.write(processed)
#     assert processed == two_liner_expected_output


def test_two_liner():
    flint_test("two_liner.py")

def test_no_fstring():
    flint_test("no_fstring_1.py")