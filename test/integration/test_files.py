""" Test str processors on actual file contents """
import os
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
    with open(filepath, "w") as f:
        f.write(txt)


def try_on_file(filename: str, multiline):
    """ Given a file name (something.py) find this file in test/integration/samples_in,
    run flint_str on its content, write result to test/integration/actual_out/something.py,
    and compare the result with test/integration/expected_out/something.py"""
    txt_in = read_in(filename)
    out, edits = fstringify_code_by_line(txt_in, multiline=multiline, len_limit=None)

    write_output_file(filename, out)
    return out, read_expected(filename)


def test_fstringify(filename):
    out, expected = try_on_file(filename, multiline=True)
    assert out == expected
