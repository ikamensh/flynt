"""This module parses the command line arguments and passes them to flynt.api.fstringify."""

import argparse
import sys
import warnings

from flynt.api import fstringify, fstringify_code_by_line
from flynt import state
from flynt import __version__
from flynt.pyproject_finder import find_pyproject_toml, parse_pyproject_toml


def main():
    return sys.exit(run_flynt_cli())


def run_flynt_cli():
    """"""
    parser = argparse.ArgumentParser(
        description=f"flynt v.{__version__}", add_help=True
    )

    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="run with verbose output",
        default=False,
    )
    verbosity_group.add_argument(
        "-q", "--quiet", action="store_true", help="run without output", default=False
    )

    multiline_group = parser.add_mutually_exclusive_group()
    multiline_group.add_argument(
        "--no-multiline",
        action="store_true",
        help="convert only single line expressions",
        default=False,
    )
    multiline_group.add_argument(
        "-ll",
        "--line-length",
        action="store",
        help="for expressions spanning multiple lines, convert only if "
        "the resulting single line will fit into the line length limit. "
        "Default value is 88 characters.",
        default=88,
    )

    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        default=False,
        help="Do not change the files in-place and print the diff instead. "
        "Note that this must be used in conjunction with '--fail-on-change' when "
        "used for linting purposes.",
    )

    parser.add_argument(
        "-s",
        "--string",
        action="store_true",
        default=False,
        help="Interpret the input as a Python code snippet and print the converted version. "
        "The snippet must use single quotes or escaped double quotes. ",
    )

    parser.add_argument(
        "-tc",
        "--transform-concats",
        action="store_true",
        default=False,
        help="Replace string concatenations (defined as + operations involving string literals) "
        "with f-strings. Available only if flynt is installed with 3.8+ interpreter.",
    )

    parser.add_argument(
        "-f",
        "--fail-on-change",
        action="store_true",
        default=False,
        help="Fail when changing files (for linting purposes)",
    )

    parser.add_argument(
        "-a",
        "--aggressive",
        action="store_true",
        default=False,
        help="Include conversions with potentially changed behavior.",
    )

    parser.add_argument(
        "-e",
        "--exclude",
        action="store",
        nargs="+",
        help="ignore files with given strings in it's absolute path.",
    )

    parser.add_argument(
        "src", action="store", nargs="*", help="source file(s) or directory"
    )

    parser.add_argument(
        "--version",
        action="store_true",
        default=False,
        help="Print the current version number and exit.",
    )
    args = parser.parse_args()

    if args.version:
        print(__version__)
        return 0
    elif not args.src:
        print("flynt: error: the following arguments are required: src")
        parser.print_usage()
        return 1

    salutation = f"Running flynt v.{__version__}"
    toml_file = find_pyproject_toml(tuple(args.src))
    if toml_file:
        salutation += f"\nUsing config file at {toml_file}"
        cfg = parse_pyproject_toml(toml_file)
        supported_args = list(args.__dict__.keys())
        redundant = set(cfg.keys()) - set(supported_args)
        if redundant:
            supported_args.sort()
            warnings.warn(
                f"Unknown config options: {redundant}. "
                f"This might be a spelling problem. "
                f"Supported options are: {supported_args}"
            )
        parser.set_defaults(**cfg)
        args = parser.parse_args()

    if not args.string:
        print(salutation)

    if args.dry_run:
        print("Running flynt in dry-run mode. No files will be changed.")

    if args.transform_concats and sys.version_info < (3, 8):
        raise Exception(
            f"""Transforming string concatenations is only possible with flynt
                installed to a python3.8+ interpreter. Currently using {sys.version_info}."""
        )

    if args.verbose and not args.string:
        print(f"Using following options: {args}")

    state.aggressive = args.aggressive
    state.verbose = args.verbose
    state.quiet = args.quiet
    state.dry_run = args.dry_run

    if args.string:
        converted, _ = fstringify_code_by_line(
            " ".join(args.src),
            multiline=not args.no_multiline,
            len_limit=int(args.line_length),
        )
        print(converted)
        return 0
    else:
        return fstringify(
            args.src,
            excluded_files_or_paths=args.exclude,
            multiline=not args.no_multiline,
            len_limit=int(args.line_length),
            fail_on_changes=args.fail_on_change,
            transform_concat=args.transform_concats,
        )
