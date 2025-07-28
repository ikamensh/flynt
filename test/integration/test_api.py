import os
import json
import shutil

import pytest

from flynt import api
from flynt.api import _fstringify_file, _resolve_files
from flynt.state import State

# These "files" are byte-string constants instead of actual files to prevent e.g. Git or text editors from accidentally changing the encoding
invalid_unicode = b"# This is not valid unicode: " + bytes([0xFF, 0xFF])
mixed_line_endings_before = b"'{}'.format(1)\n'{}'.format(2)# Linux line ending\n'{}'.format(3)# Windows line ending\r\n"
mixed_line_endings_after = (
    b"f'{1}'\nf'{2}'# Linux line ending\nf'{3}'# Windows line ending\r\n"
)
fake_path_tree = (
    r"src/flynt/test/unix/code.py",
    r"src/flynt/test/unix/exclude/code.py",
    r"src/flynt/test/win/code.py",
    r"src/flynt/test/win/exclude/code.py",
    r"src/flynt/test/mixed/code.py",
    r"src/flynt/test/mixed/exclude/code.py",
)
uniform_path_exclude = (
    r"test/unix/exclude",
    r"test\win\exclude",
    r"test/mixed\exclude",
)
uniform_path_count_result = len(fake_path_tree) - len(uniform_path_exclude)


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
def invalid_unicode_file(tmpdir):
    folder = os.path.dirname(__file__)
    tmp_path = os.path.join(tmpdir, "invalid_unicode.py")

    with open(tmp_path, "wb") as f:
        f.write(invalid_unicode)

    yield tmp_path


@pytest.fixture()
def mixed_line_endings_file(tmpdir):
    folder = os.path.dirname(__file__)
    tmp_path = os.path.join(tmpdir, "mixed_line_endings.py")
    with open(tmp_path, "wb") as file:
        file.write(mixed_line_endings_before)

    yield tmp_path


def test_py2(py2_file):
    with open(py2_file) as f:
        content_before = f.read()

    result = _fstringify_file(py2_file, state=State(multiline=True, len_limit=1000))

    with open(py2_file) as f:
        content_after = f.read()

    assert not result
    assert content_after == content_before


def test_invalid_unicode(invalid_unicode_file):
    result = _fstringify_file(
        invalid_unicode_file, state=State(multiline=True, len_limit=1000)
    )

    with open(invalid_unicode_file, "rb") as f:
        content_after = f.read()

    assert not result
    assert content_after == invalid_unicode


def test_works(formattable_file):
    with open(formattable_file) as f:
        content_before = f.read()

    result = _fstringify_file(
        formattable_file, state=State(multiline=True, len_limit=1000)
    )

    with open(formattable_file) as f:
        content_after = f.read()

    assert result.n_changes
    assert content_after != content_before


def test_break_safe(formattable_file, monkeypatch):
    with open(formattable_file) as f:
        content_before = f.read()

    def broken_fstringify_by_line(*args, **kwargs):
        return "Hello World", 42

    monkeypatch.setattr(api, "fstringify_code_by_line", broken_fstringify_by_line)

    result = _fstringify_file(
        formattable_file, state=State(multiline=True, len_limit=1000)
    )

    with open(formattable_file) as f:
        content_after = f.read()

    assert not result
    assert content_after == content_before


def test_catches_subtle(formattable_file, monkeypatch):
    with open(formattable_file) as f:
        content_before = f.read()

    def broken_fstringify_by_line(*args, **kwargs):
        return "a = 42", 42

    monkeypatch.setattr(api, "fstringify_code_by_line", broken_fstringify_by_line)

    result = _fstringify_file(
        formattable_file, state=State(multiline=True, len_limit=1000)
    )

    with open(formattable_file) as f:
        content_after = f.read()

    assert not result
    assert content_after == content_before


def test_dry_run(formattable_file, monkeypatch):
    with open(formattable_file) as f:
        content_before = f.read()

    result = _fstringify_file(
        formattable_file, state=State(multiline=True, len_limit=1000, dry_run=True)
    )

    with open(formattable_file) as f:
        content_after = f.read()

    assert result.n_changes
    assert content_after == content_before


def test_mixed_line_endings(mixed_line_endings_file):
    result = _fstringify_file(
        mixed_line_endings_file, state=State(multiline=True, len_limit=1000)
    )

    with open(mixed_line_endings_file, "rb") as f:
        content_after = f.read()

    assert result.n_changes
    assert content_after == mixed_line_endings_after


@pytest.fixture()
def bom_file(tmpdir):
    folder = os.path.dirname(__file__)
    source_path = os.path.join(folder, "samples_in", "bom.py")
    tmp_path = os.path.join(tmpdir, "input.py")

    shutil.copy2(source_path, tmp_path)
    yield tmp_path


def test_bom(bom_file):
    """Test on a file with Byte order mark https://en.wikipedia.org/wiki/Byte_order_mark

    It's possible to verify that a file has bom using `file` unix utility."""

    result = _fstringify_file(bom_file, state=State(multiline=True, len_limit=1000))
    assert result.n_changes


@pytest.fixture()
def fake_folder_tree(tmpdir):
    folder = os.path.join(tmpdir, "fake_tree")
    for fake_file in fake_path_tree:
        tmp_path = os.path.join(folder, fake_file)
        os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
        with open(tmp_path, "wb") as file:
            file.write(b"")

    return folder


def test_uniform_path(fake_folder_tree):
    """Test if the arguments for excluding path is depending of the OS path separator."""

    result = _resolve_files([fake_folder_tree], uniform_path_exclude, State())
    assert len(result) == uniform_path_count_result


def test_fstringify_files_charcount(tmp_path, monkeypatch):
    source = "'{}'.format(1)\n"
    f = tmp_path / "a.py"
    with open(f, "w", newline="") as fh:
        fh.write(source)

    captured = {}

    def fake_print_report(
        state,
        found_files,
        changed_files,
        total_cc_new,
        total_cc_original,
        total_expr,
        total_time,
    ):
        captured["new"] = total_cc_new
        captured["orig"] = total_cc_original

    monkeypatch.setattr(api, "_print_report", fake_print_report)

    state = State(report=True)
    api.fstringify_files([str(f)], state)

    assert captured["orig"] == len(source)
    assert captured["new"] == len("f'{1}'\n")


def _write_notebook(path: str) -> None:
    """Create a simple notebook with one formattable code cell."""
    nb = {
        "cells": [
            {"cell_type": "code", "source": ["print('{}'.format(1))\n"]},
            {"cell_type": "markdown", "source": ["# header"]},
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f)


def test_notebook_ignored_without_flag(tmp_path):
    """Without the notebook flag ipynb files were previously skipped."""
    nb = tmp_path / "t.ipynb"
    _write_notebook(nb)
    result = _fstringify_file(str(nb), State())
    assert result is None
    with open(nb) as fh:
        data = json.load(fh)
    assert "format(1)" in "".join(data["cells"][0]["source"])


def test_notebook_conversion(tmp_path):
    """With the notebook flag enabled code cells are converted."""
    nb = tmp_path / "t.ipynb"
    _write_notebook(nb)
    result = _fstringify_file(str(nb), State(process_notebooks=True))
    assert result and result.n_changes == 1
    with open(nb) as fh:
        data = json.load(fh)
    assert "f'{1}'" in "".join(data["cells"][0]["source"])
