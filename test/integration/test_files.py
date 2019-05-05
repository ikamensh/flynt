""" Test str processors on actual file contents """
import os
from typing import Callable, Tuple
import pytest
import config

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

def write_output_file(dirname, name, txt):
    proc_dir = os.path.join(out_dir, dirname)
    os.makedirs(proc_dir, exist_ok=True)
    filepath = os.path.join(proc_dir, name)
    with open(filepath, 'w') as f:
        f.write(txt)

def _fs_tst(proc_name: str, processor: Callable, filename: str):
    """ Given a file name (something.py) find this file in test/integration/samples_in,
    run flint_str on its content, write result to test/integration/actual_out/something.py,
    and compare the result with test/integration/expected_out/something.py"""
    txt_in = read_in(filename)
    out = processor(txt_in)

    write_output_file(proc_name, os.path.join(filename), out)
    return out, read_expected(filename)

from flint.api import flint_str
from fstringify.process import fstringify_code_by_line

@pytest.fixture(params=["two_liner.py",
                        "no_fstring_1.py",
                        "no_fstring_2.py",
                        "simple.py",
                        "simple_start.py",
                        "simple_comment.py",
                        "simple_format.py",
                        "simple_percent.py",
                        "simple_percent_comment.py",
                        "multiple.py",
                        "some_named.py",
                        "all_named.py",
                        "first_string.py"])
def filename(request):
    yield request.param

@pytest.mark.skip(reason="no hope in flint.")
def test_flint(filename):
    out, expected = _fs_tst("flint", flint_str, filename)
    assert out == expected

def test_fstringify(filename):
    out, expected = _fs_tst("fstringify", fstringify_code_by_line, filename)
    assert out == expected