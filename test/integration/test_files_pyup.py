""" Test str processors on actual file contents """
import os
import config
from flynt.api import fstringify_file


int_test_dir = os.path.join(config.home, "test/integration/")

in_dir = os.path.join(int_test_dir, "samples_in")
out_dir = os.path.join(int_test_dir, "actual_out")
expected_dir = os.path.join(int_test_dir, "expected_out")

os.makedirs(out_dir, exist_ok=True)


def read_in(name) -> str:
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
    return filepath


def try_on_file(filename: str):
    """ Given a file name (something.py) find this file in test/integration/samples_in,
    run flint_str on its content, write result to test/integration/actual_out/something.py,
    and compare the result with test/integration/expected_out/something.py"""
    txt_in = read_in(filename)
    result_path = write_output_file(filename, txt_in)

    fstringify_file(result_path, multiline=True, len_limit=79, pyup=True)

    with open(result_path) as f:
        out = f.read()

    return out, read_expected(filename)


def test_fstringify():
    out, expected = try_on_file("pyup.py")
    assert out == expected
