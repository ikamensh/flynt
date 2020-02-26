import os
import shutil

import pytest

from flynt import api
from flynt.api import fstringify_file


@pytest.fixture()
def formattable_file(tmpdir):
    folder = os.path.dirname(__file__)
    source_path = os.path.join(folder, "samples_in", "first_string.py")
    tmp_path = os.path.join(tmpdir, "input.py")

    shutil.copy2(source_path, tmp_path)
    yield tmp_path


@pytest.fixture()
def py2_file(tmpdir):
    folder = os.path.dirname(__file__)
    py2_path = os.path.join(folder, "samples_in", "py2.py2")
    tmp_path = os.path.join(tmpdir, "py2.py2")

    shutil.copy2(py2_path, tmp_path)
    yield tmp_path


def test_py2(py2_file):

    with open(py2_file) as f:
        content_before = f.read()

    modified, _, _, _ = fstringify_file(py2_file, True, 1000)

    with open(py2_file) as f:
        content_after = f.read()

    assert not modified
    assert content_after == content_before


def test_works(formattable_file):

    with open(formattable_file) as f:
        content_before = f.read()

    modified, _, _, _ = fstringify_file(formattable_file, True, 1000)

    with open(formattable_file) as f:
        content_after = f.read()

    assert modified
    assert content_after != content_before


def test_break_safe(formattable_file, monkeypatch):

    with open(formattable_file) as f:
        content_before = f.read()

    def broken_fstringify_by_line(*args, **kwargs):
        return "Hello World", 42

    monkeypatch.setattr(api, "fstringify_code_by_line", broken_fstringify_by_line)

    modified, _, _, _ = fstringify_file(formattable_file, True, 1000)

    with open(formattable_file) as f:
        content_after = f.read()

    assert not modified
    assert content_after == content_before


def test_catches_subtle(formattable_file, monkeypatch):

    with open(formattable_file) as f:
        content_before = f.read()

    def broken_fstringify_by_line(*args, **kwargs):
        return "a = 42", 42

    monkeypatch.setattr(api, "fstringify_code_by_line", broken_fstringify_by_line)

    modified, _, _, _ = fstringify_file(formattable_file, True, 1000)

    with open(formattable_file) as f:
        content_after = f.read()

    assert not modified
    assert content_after == content_before
