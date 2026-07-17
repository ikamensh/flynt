"""Port of the original test_cli.py / test_api.py / test_notebook_file.py
integration tests, driving the real flynt-rs binary via subprocess.

In-process Python tests that monkeypatch flynt internals (test_break_safe,
test_catches_subtle, test_fstringify_files_charcount, test_uniform_path)
are covered as Rust unit tests in src/api.rs instead — see README there.
"""

import json
import shutil
import subprocess

import pytest

from conftest import BINARY, INT_DIR

VERSION = "2.0.0-beta.1"  # CARGO_PKG_VERSION; PyPI equivalent is 2.0.0b1

valid_snippets = [
    ("'{}'.format(x) + '{}'.format(y)", "f'{x}' + f'{y}'"),
    (
        "['{}={}'.format(key, value) for key, value in x.items()]",
        "[f'{key}={value}' for key, value in x.items()]",
    ),
    (
        '["{}={}".format(key, value) for key, value in x.items()]',
        '[f"{key}={value}" for key, value in x.items()]',
    ),
]
invalid_snippets = [
    (
        "This ! isn't <> valid .. Python $ code",
        "This ! isn't <> valid .. Python $ code",
    ),
]


def run_cli(args, stdin=None):
    return subprocess.run(
        [str(BINARY), *args], input=stdin, capture_output=True, text=True, encoding="utf-8"
    )


def test_cli_no_args():
    p = run_cli([])
    assert p.returncode == 1
    assert "the following arguments are required: src" in p.stdout


def test_cli_version():
    p = run_cli(["--version"])
    assert p.returncode == 0
    assert p.stdout == f"{VERSION}\n"
    assert p.stderr == ""


@pytest.mark.parametrize("code_in, code_out", [*valid_snippets, *invalid_snippets])
def test_cli_string_quoted(code_in, code_out):
    p = run_cli(["-s", code_in])
    assert p.returncode == 0
    assert p.stdout.strip() == code_out
    assert p.stderr == ""


@pytest.mark.parametrize("code_in, code_out", [*valid_snippets, *invalid_snippets])
def test_cli_string_unquoted(code_in, code_out):
    p = run_cli(["-s", *code_in.split()])
    assert p.returncode == 0
    assert p.stdout.strip() == code_out
    assert p.stderr == ""


def test_cli_string_supports_flags():
    p = run_cli(
        ["-tc", "--string", "test_string = 'This' + ' ' + 'may' + ' ' + 'not' + ' ' + 'work'"]
    )
    assert p.returncode == 0
    assert p.stdout.strip() == 'test_string = "This may not work"'
    assert p.stderr == ""


@pytest.mark.parametrize("code_in, code_out", valid_snippets)
def test_cli_stdin(code_in, code_out):
    p = run_cli(["-"], stdin=code_in + "\n")
    assert p.returncode == 0
    assert p.stdout.strip() == code_out
    assert p.stderr == ""


@pytest.mark.parametrize(
    "sample_file",
    ["all_named.py", "first_string.py", "percent_dict.py", "multiline_limit.py"],
)
def test_cli_dry_run(sample_file, tmp_path):
    source_path = INT_DIR / "samples_in" / sample_file
    expected_path = INT_DIR / "expected_out" / sample_file
    source_lines = source_path.read_text(encoding="utf-8").splitlines(keepends=True)
    converted_lines = expected_path.read_text(encoding="utf-8").splitlines(keepends=True)
    work = tmp_path / sample_file
    shutil.copy2(source_path, work)

    p = run_cli(["--dry-run", str(work)])
    assert p.returncode == 0
    for line in source_lines:
        if line not in converted_lines:
            assert f"-{line.strip()}" in p.stdout, "Original source line missing"
    for line in converted_lines:
        if line not in source_lines:
            assert f"+{line.strip()}" in p.stdout, "Converted source line missing"
    assert p.stderr == ""
    assert work.read_text(encoding="utf-8") == source_path.read_text(encoding="utf-8"), "dry-run must not modify"


@pytest.mark.parametrize(
    "sample_file",
    ["all_named.py", "first_string.py", "percent_dict.py", "multiline_limit.py"],
)
def test_cli_stdout(sample_file):
    source_path = INT_DIR / "samples_in" / sample_file
    expected_path = INT_DIR / "expected_out" / sample_file
    expected_lines = [l.rstrip() for l in expected_path.read_text(encoding="utf-8").splitlines()]

    p = run_cli(["--stdout", str(source_path)])
    assert p.returncode == 0
    actual_lines = p.stdout.rstrip().splitlines()
    for line in expected_lines:
        assert line in actual_lines
    for line in actual_lines:
        assert line in expected_lines
    assert p.stderr == ""


def test_cli_report_flag():
    source_path = INT_DIR / "samples_in" / "all_named.py"
    p = run_cli(["--dry-run", "--report", str(source_path)])
    assert p.returncode == 0
    assert "Flynt run has finished. Stats:" in p.stdout
    assert p.stderr == ""


# ---- test_api.py cases (file-level, via the real binary) ----

STATE_ARGS = ["-ll", "1000"]  # State(multiline=True, len_limit=1000)


def test_py2(tmp_path):
    src = INT_DIR / "samples_in" / "py2.py2"
    work = tmp_path / "py2.py2"
    shutil.copy2(src, work)
    before = work.read_bytes()
    run_cli([*STATE_ARGS, str(work)])
    assert work.read_bytes() == before


def test_invalid_unicode(tmp_path):
    invalid = b"# This is not valid unicode: " + bytes([0xFF, 0xFF])
    work = tmp_path / "invalid_unicode.py"
    work.write_bytes(invalid)
    run_cli([*STATE_ARGS, str(work)])
    assert work.read_bytes() == invalid


def test_works(tmp_path):
    src = INT_DIR / "samples_in" / "first_string.py"
    work = tmp_path / "input.py"
    shutil.copy2(src, work)
    before = work.read_text(encoding="utf-8")
    p = run_cli([*STATE_ARGS, str(work)])
    assert p.returncode == 0
    assert work.read_text(encoding="utf-8") != before


def test_dry_run_leaves_file(tmp_path):
    src = INT_DIR / "samples_in" / "first_string.py"
    work = tmp_path / "input.py"
    shutil.copy2(src, work)
    before = work.read_text(encoding="utf-8")
    run_cli([*STATE_ARGS, "--dry-run", str(work)])
    assert work.read_text(encoding="utf-8") == before


def test_mixed_line_endings(tmp_path):
    before = b"'{}'.format(1)\n'{}'.format(2)# Linux line ending\n'{}'.format(3)# Windows line ending\r\n"
    after = b"f'{1}'\nf'{2}'# Linux line ending\nf'{3}'# Windows line ending\r\n"
    work = tmp_path / "mixed.py"
    work.write_bytes(before)
    run_cli([*STATE_ARGS, str(work)])
    assert work.read_bytes() == after


def test_bom(tmp_path):
    src = INT_DIR / "samples_in" / "bom.py"
    work = tmp_path / "input.py"
    shutil.copy2(src, work)
    p = run_cli([*STATE_ARGS, str(work)])
    assert p.returncode == 0
    raw = work.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf"), "BOM must be preserved"
    assert b"f'" in raw or b'f"' in raw, "file must be converted"


def test_fail_on_change(tmp_path):
    src = INT_DIR / "samples_in" / "first_string.py"
    work = tmp_path / "input.py"
    shutil.copy2(src, work)
    p = run_cli(["--fail-on-change", "--dry-run", str(work)])
    assert p.returncode == 1


# ---- test_notebook_file.py ----


def test_sample_notebook(tmp_path):
    src = INT_DIR / "samples_in" / "simple.ipynb"
    expected = INT_DIR / "expected_out" / "simple.ipynb"
    work = tmp_path / "simple.ipynb"
    shutil.copy2(src, work)
    p = run_cli(["-nb", str(work)])
    assert p.returncode == 0
    assert json.loads(work.read_text(encoding="utf-8")) == json.loads(expected.read_text(encoding="utf-8"))


def test_notebook_ignored_without_flag(tmp_path):
    src = INT_DIR / "samples_in" / "simple.ipynb"
    work = tmp_path / "simple.ipynb"
    shutil.copy2(src, work)
    before = work.read_bytes()
    run_cli([str(work)])
    assert work.read_bytes() == before
