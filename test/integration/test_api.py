import os
import shutil

import pytest

from flynt import api
from flynt import state
from flynt.api import _fstringify_file
from flynt.api import _auto_detect_line_ending


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


@pytest.fixture()
def windows_file(tmpdir):
    folder = os.path.dirname(__file__)
    windows_file_path = os.path.join(folder, "samples_in", "windows_line_endings.py")
    tmp_path = os.path.join(tmpdir, "windows_line_endings.py")

    shutil.copy2(windows_file_path, tmp_path)
    yield tmp_path


def test_py2(py2_file):

    with open(py2_file) as f:
        content_before = f.read()

    modified, _, _, _ = _fstringify_file(py2_file, True, 1000)

    with open(py2_file) as f:
        content_after = f.read()

    assert not modified
    assert content_after == content_before
    assert _auto_detect_line_ending(content_before) == "\n"
    assert _auto_detect_line_ending(content_after) == "\n"


def test_works(formattable_file):

    with open(formattable_file) as f:
        content_before = f.read()

    modified, _, _, _ = _fstringify_file(formattable_file, True, 1000)

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

    modified, _, _, _ = _fstringify_file(formattable_file, True, 1000)

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

    modified, _, _, _ = _fstringify_file(formattable_file, True, 1000)

    with open(formattable_file) as f:
        content_after = f.read()

    assert not modified
    assert content_after == content_before


def test_dry_run(formattable_file, monkeypatch):
    monkeypatch.setattr(state, "dry_run", True)
    with open(formattable_file) as f:
        content_before = f.read()

    modified, _, _, _ = _fstringify_file(formattable_file, True, 1000)

    with open(formattable_file) as f:
        content_after = f.read()

    assert modified
    assert content_after == content_before


def test_windows_line_endings(windows_file):
    with open(windows_file, "rb") as f:
        content_before = f.read().decode()

    modified, _, _, _ = _fstringify_file(windows_file, True, 1000)

    with open(windows_file, "rb") as f:
        content_after = f.read().decode()

    assert _auto_detect_line_ending(content_before) == "\r\n"
    assert _auto_detect_line_ending(content_after) == "\r\n"
    assert not modified
    assert content_after == content_before


def test_unix_line_endings(py2_file):
    with open(py2_file) as f:
        content_before = f.read()

    modified, _, _, _ = _fstringify_file(py2_file, True, 1000)

    with open(py2_file) as f:
        content_after = f.read()

    assert _auto_detect_line_ending(content_before) == "\n"
    assert _auto_detect_line_ending(content_after) == "\n"
    assert not modified
    assert content_after == content_before
