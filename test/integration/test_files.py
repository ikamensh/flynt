""" Test str processors on actual file contents """
import os
import pytest
import config
from flynt.process import fstringify_code_by_line


int_test_dir = os.path.join(config.home, "test/integration/")

in_dir = os.path.join(int_test_dir, "samples_in")
out_dir = os.path.join(int_test_dir, "actual_out")
expected_dir = os.path.join(int_test_dir, "expected_out")

os.makedirs(out_dir, exist_ok=True)


def read_in(name):
    filepath = os.path.join(in_dir, name)
    with open(filepath) as f:
        txt = f.read()

    return txt

def read_expected(name):
    filepath = os.path.join(expected_dir, name)
    with open(filepath) as f:
        txt = f.read()

    return txt

def write_output_file(name, txt):
    filepath = os.path.join(out_dir, name)
    with open(filepath, 'w') as f:
        f.write(txt)

def try_on_file(filename: str, multiline):
    """ Given a file name (something.py) find this file in test/integration/samples_in,
    run flint_str on its content, write result to test/integration/actual_out/something.py,
    and compare the result with test/integration/expected_out/something.py"""
    txt_in = read_in(filename)
    out, edits = fstringify_code_by_line(txt_in, transform_multiline=multiline)

    write_output_file(filename, out)
    return out, read_expected(filename)


all_files = pytest.fixture(params=["all_named.py",
                        "first_string.py",
                        "def_empty_line.py",
                        "digit_ordering.py",
                        "CantAffordActiveException.py",
                        "hard_percent.py",
                        "indexed_fmt_name.py",
                        "indexed_percent.py",
                        "long.py",
                        "multiline.py",
                        "multiline_1.py",
                        "multiline_2.py",
                        "multiline_3.py",
                        "multiline_twice.py",
                        "named_inverse.py",
                        "no_fstring_1.py",
                        "no_fstring_2.py",
                        "percent_op.py",
                        "percent_numerics.py",
                        "percent_strings.py",
                        "simple.py",
                        "simple_indent.py",
                        "simple_start.py",
                        "simple_comment.py",
                        "simple_docstring.py",
                        "simple_format.py",
                        "simple_format_double_brace.py",
                        "simple_percent.py",
                        "simple_percent_comment.py",
                        "simple_str_newline.py",
                        "simple_str_tab.py",
                        "simple_str_return.py",
                        "slash_quotes.py",
                        "some_named.py",
                        "string_in_string.py",
                        "raw_string.py",
                        "tuple_in_list.py"
                        ])

# @pytest.fixture(params=["multiline_2.py"])
@all_files
def filename(request):
    yield request.param

def test_fstringify(filename):
    out, expected = try_on_file(filename, multiline=True)
    assert out == expected


def try_on_file_expect_no_change(filename: str, multiline):
    """ Given a file name (something.py) find this file in test/integration/samples_in,
    run flint_str on its content, write result to test/integration/actual_out/something.py,
    and compare the result with test/integration/expected_out/something.py"""
    txt_in = read_in(filename)
    out, edits = fstringify_code_by_line(txt_in, transform_multiline=multiline)
    return out, txt_in

multiline_transform_files = pytest.fixture(params=[
                                "multiline.py",
                                "multiline_1.py",
                                "multiline_2.py",
                                "multiline_3.py",
                                ])
@multiline_transform_files
def multiline_filename(request):
    yield request.param

def test_single_line(multiline_filename):
    out, expected = try_on_file_expect_no_change(multiline_filename, multiline=False)
    assert out == expected