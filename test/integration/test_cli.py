import io
import os
import sys

import pytest

import flynt
from flynt.cli import run_flynt_cli


def test_cli_no_args(capsys):
    """
    With no arguments, it should require src to be set
    """
    return_code = run_flynt_cli([])
    assert return_code == 1

    out, err = capsys.readouterr()
    assert "the following arguments are required: src" in out


def test_cli_version(capsys):
    """
    With --version set, it should only print the version
    """
    return_code = run_flynt_cli(["--version"])
    assert return_code == 0

    out, err = capsys.readouterr()
    assert out == f"{flynt.__version__}\n"
    assert err == ""


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


@pytest.mark.parametrize("code_in, code_out", [*valid_snippets, *invalid_snippets])
def test_cli_string_quoted(capsys, code_in, code_out):
    """
    Tests an invocation with quotes, like:

        flynt -s "some code snippet"

    Then the src argument will be ["some code snippet"].
    """
    return_code = run_flynt_cli(["-s", code_in])
    assert return_code == 0

    out, err = capsys.readouterr()
    assert out.strip() == code_out
    assert err == ""


@pytest.mark.parametrize("code_in, code_out", [*valid_snippets, *invalid_snippets])
def test_cli_string_unquoted(capsys, code_in, code_out):
    """
    Tests an invocation with no quotes, like:

        flynt -s some code snippet

    Then the src argument will be ["some", "code", "snippet"].
    """
    return_code = run_flynt_cli(["-s", *code_in.split()])
    assert return_code == 0

    out, err = capsys.readouterr()
    assert out.strip() == code_out
    assert err == ""


@pytest.mark.skipif(sys.version_info < (3, 9), reason="requires python3.9 or higher")
def test_cli_string_supports_flags(capsys):
    """
    Tests a --string invocation also does additional transformations.

    See https://github.com/ikamensh/flynt/issues/162
    """
    return_code = run_flynt_cli(
        [
            "-tc",
            "--string",
            "test_string = 'This' + ' ' + 'may' + ' ' + 'not' + ' ' + 'work'",
        ]
    )
    assert return_code == 0
    out, err = capsys.readouterr()
    assert out.strip() == 'test_string = f"This may not work"'
    assert err == ""


@pytest.mark.parametrize("code_in, code_out", valid_snippets)
def test_cli_stdin(monkeypatch, capsys, code_in, code_out):
    """
    Tests a stdin/stdout invocation, like:
        echo snippet | flynt -
    """
    monkeypatch.setattr("sys.stdin", io.StringIO(code_in + os.linesep))
    return_code = run_flynt_cli(["-"])
    assert return_code == 0
    out, err = capsys.readouterr()
    assert out.strip() == code_out
    assert err == ""


@pytest.mark.parametrize(
    "sample_file",
    ["all_named.py", "first_string.py", "percent_dict.py", "multiline_limit.py"],
)
def test_cli_dry_run(capsys, sample_file):
    """
    Tests the --dry-run option with a few files, all changed lines should be shown in the diff
    """
    # Get input/output paths and read them
    folder = os.path.dirname(__file__)
    source_path = os.path.join(folder, "samples_in", sample_file)
    expected_path = os.path.join(folder, "expected_out", sample_file)
    with open(source_path) as file:
        source_lines = file.readlines()
    with open(expected_path) as file:
        converted_lines = file.readlines()

    # Run the CLI
    return_code = run_flynt_cli(["--dry-run", source_path])
    assert return_code == 0

    # Check that the output includes all changed lines, and the farewell message
    out, err = capsys.readouterr()
    for line in source_lines:
        if line not in converted_lines:
            assert f"-{line.strip()}" in out, "Original source line missing from output"
    for line in converted_lines:
        if line not in source_lines:
            assert f"+{line.strip()}" in out, (
                "Converted source line missing from output"
            )

    assert err == ""


@pytest.mark.parametrize(
    "sample_file",
    ["all_named.py", "first_string.py", "percent_dict.py", "multiline_limit.py"],
)
def test_cli_stdout(capsys, sample_file):
    """
    Tests the --stdout option with a few files
    """
    # Get input/output paths and read them
    folder = os.path.dirname(__file__)
    source_path = os.path.join(folder, "samples_in", sample_file)
    expected_path = os.path.join(folder, "expected_out", sample_file)
    with open(expected_path) as file:
        # file.readlines() returns lines with "\n" endings, which we must strip
        # away for comparing with out.splitlines() which removes line endings.
        expected_lines = [line.rstrip() for line in file.readlines()]

    # Run the CLI
    return_code = run_flynt_cli(["--stdout", source_path])
    assert return_code == 0

    # Check that the output includes the output code, and no farewell message
    out, err = capsys.readouterr()
    actual_lines = out.rstrip().splitlines()
    for line in expected_lines:
        assert line in actual_lines
    for line in actual_lines:
        assert line in expected_lines
    assert err == ""


def test_cli_report_flag(capsys):
    folder = os.path.dirname(__file__)
    source_path = os.path.join(folder, "samples_in", "all_named.py")

    return_code = run_flynt_cli(["--dry-run", "--report", source_path])
    assert return_code == 0

    out, err = capsys.readouterr()
    assert "Flynt run has finished. Stats:" in out
    assert err == ""
