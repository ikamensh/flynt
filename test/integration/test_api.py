import os
import shutil

import pytest

from flynt import api, state
from flynt.api import _fstringify_file

# These "files" are byte-string constants instead of actual files to prevent e.g. Git or text editors from accidentally changing the encoding
invalid_unicode = b"# This is not valid unicode: " + bytes([0xFF, 0xFF])
mixed_line_endings_before = b"'{}'.format(1)\n'{}'.format(2)# Linux line ending\n'{}'.format(3)# Windows line ending\r\n"
mixed_line_endings_after = (
    b"f'{1}'\nf'{2}'# Linux line ending\nf'{3}'# Windows line ending\r\n"
)


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

    modified, _, _, _ = _fstringify_file(py2_file, True, 1000)

    with open(py2_file) as f:
        content_after = f.read()

    assert not modified
    assert content_after == content_before


def test_invalid_unicode(invalid_unicode_file):
    modified, _, _, _ = _fstringify_file(invalid_unicode_file, True, 1000)

    with open(invalid_unicode_file, "rb") as f:
        content_after = f.read()

    assert not modified
    assert content_after == invalid_unicode


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


def test_mixed_line_endings(mixed_line_endings_file):
    modified, _, _, _ = _fstringify_file(mixed_line_endings_file, True, 1000)

    with open(mixed_line_endings_file, "rb") as f:
        content_after = f.read()

    assert modified
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

    modified, _, _, _ = _fstringify_file(bom_file, True, 1000)
    assert modified
