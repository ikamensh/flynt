import argparse
import os

import pytest

import flynt
from flynt.cli import run_flynt_cli
from flynt.cli_messages import farewell_message


class ArgumentParser:
    """
    Mock class for argparse.ArgumentParser

    Parameters:
        shadow_parser: a real argparse.ArgumentParser
        parse_args_return_value: the Namespace that should be returned from parse_args.
    """

    def __init__(
        self,
        shadow_parser: argparse.ArgumentParser,
        parse_args_return_value: argparse.Namespace,
        *args,
        **kwargs,
    ):
        self.parse_args_return_value = parse_args_return_value
        self.shadow_parser = shadow_parser

    def add_mutually_exclusive_group(self):
        return MutuallyExclusiveGroup(self)

    def add_argument(self, *args, **kwargs):
        arg = self.shadow_parser.add_argument(*args, **kwargs)
        if arg.dest not in self.parse_args_return_value:
            setattr(self.parse_args_return_value, arg.dest, arg.default)
        return arg

    def print_usage(self):
        return self.shadow_parser.print_usage()

    def parse_args(self):
        return self.parse_args_return_value

    def set_defaults(self):
        pass


class MutuallyExclusiveGroup:
    """
    Mock class for argparse.MutuallyExclusiveGroup
    """

    def __init__(self, parent):
        self.parent = parent

    def add_argument(self, *args, **kwargs):
        return self.parent.add_argument(*args, **kwargs)


def run_cli_test(monkeypatch, **kwargs):
    """
    Runs the CLI, setting arguments according to **kwargs.
    For example, running with version=True is like passing the --version argument to the CLI.
    """
    shadow_parser = argparse.ArgumentParser()
    parse_args_return_value = argparse.Namespace(**kwargs)

    def argument_parser_mock(*args, **kwargs):
        return ArgumentParser(shadow_parser, parse_args_return_value, *args, **kwargs)

    monkeypatch.setattr(argparse, "ArgumentParser", argument_parser_mock)
    return run_flynt_cli()


def test_cli_no_args(monkeypatch, capsys):
    """
    With no arguments, it should require src to be set
    """
    return_code = run_cli_test(monkeypatch)
    assert return_code == 1

    out, err = capsys.readouterr()
    assert "the following arguments are required: src" in out


def test_cli_version(monkeypatch, capsys):
    """
    With --version set, it should only print the version
    """
    return_code = run_cli_test(monkeypatch, version=True)
    assert return_code == 0

    out, err = capsys.readouterr()
    assert out == f"{flynt.__version__}\n"
    assert err == ""


# Code snippets for testing the -s/--string argument
cli_string_snippets = pytest.mark.parametrize(
    "code_in, code_out",
    [
        ("'{}'.format(x) + '{}'.format(y)", "f'{x}' + f'{y}'"),
        (
            "['{}={}'.format(key, value) for key, value in x.items()]",
            "[f'{key}={value}' for key, value in x.items()]",
        ),
        (
            '["{}={}".format(key, value) for key, value in x.items()]',
            '[f"{key}={value}" for key, value in x.items()]',
        ),
        (
            "This ! isn't <> valid .. Python $ code",
            "This ! isn't <> valid .. Python $ code",
        ),
    ],
)


@cli_string_snippets
def test_cli_string_quoted(monkeypatch, capsys, code_in, code_out):
    """
    Tests an invocation with quotes, like:

        flynt -s "some code snippet"

    Then the src argument will be ["some code snippet"].
    """
    return_code = run_cli_test(monkeypatch, string=True, src=[code_in])
    assert return_code == 0

    out, err = capsys.readouterr()
    assert out.strip() == code_out
    assert err == ""


@cli_string_snippets
def test_cli_string_unquoted(monkeypatch, capsys, code_in, code_out):
    """
    Tests an invocation with no quotes, like:

        flynt -s some code snippet

    Then the src argument will be ["some", "code", "snippet"].
    """
    return_code = run_cli_test(monkeypatch, string=True, src=code_in.split())
    assert return_code == 0

    out, err = capsys.readouterr()
    assert out.strip() == code_out
    assert err == ""


@pytest.mark.parametrize(
    "sample_file",
    ["all_named.py", "first_string.py", "percent_dict.py", "multiline_limit.py"],
)
def test_cli_dry_run(monkeypatch, capsys, sample_file):
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
    return_code = run_cli_test(monkeypatch, dry_run=True, src=[source_path])
    assert return_code == 0

    # Check that the output includes all changed lines, and the farewell message
    out, err = capsys.readouterr()
    print(out)
    for line in source_lines:
        if line not in converted_lines:
            assert f"-{line}" in out, "Original source line missing from output"
    for line in converted_lines:
        if line not in source_lines:
            assert f"+{line}" in out, "Converted source line missing from output"

    assert out.strip().endswith(farewell_message.strip())
    assert err == ""
