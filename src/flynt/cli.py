"""This module parses the command line arguments and passes them to flynt.api.fstringify."""

import argparse
import logging
import sys
import warnings
from typing import List, Optional

from flynt import __version__
from flynt.api import fstringify, fstringify_code_by_line
from flynt.pyproject_finder import find_pyproject_toml, parse_pyproject_toml
from flynt.state import State


def main():
    return sys.exit(run_flynt_cli())


def run_flynt_cli(arglist: Optional[List[str]] = None) -> int:
    """"""
    parser = argparse.ArgumentParser(
        prog="flynt",
        description=f"flynt v.{__version__}",
        add_help=True,
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
        "-q",
        "--quiet",
        action="store_true",
        help="run without stdout output",
        default=False,
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
        "--no-tp",
        "--no-transform-percent",
        dest="transform_percent",
        action="store_false",
        default=True,
        help="Don't transform %% formatting to f-strings (default: do so)",
    )

    parser.add_argument(
        "--no-tf",
        "--no-transform-format",
        dest="transform_format",
        action="store_false",
        default=True,
        help="Don't transform .format formatting to f-strings (default: do so)",
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
        "-tj",
        "--transform-joins",
        action="store_true",
        default=False,
        help="Replace static joins (where the joiner is a string literal and the joinee is a static-length list) "
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
        "src",
        action="store",
        nargs="*",
        help="source file(s) or directory",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        default=False,
        help="Print the current version number and exit.",
    )
    args = parser.parse_args(arglist)

    if args.version:
        print(__version__)
        return 0
    if not args.src:
        print("flynt: error: the following arguments are required: src")
        parser.print_usage()
        return 1

    if args.transform_concats and sys.version_info < (3, 8):
        raise Exception(
            f"""Transforming string concatenations is only possible with flynt
                installed to a python3.8+ interpreter. Currently using {sys.version_info}.""",
        )

    if args.transform_joins and sys.version_info < (3, 8):
        raise Exception(
            f"""Transforming joins is only possible with flynt
                installed to a python3.8+ interpreter. Currently using {sys.version_info}.""",
        )

    logging.basicConfig(
        format="%(message)s",
        level=(logging.DEBUG if args.verbose else logging.CRITICAL),
    )

    state = State(
        aggressive=args.aggressive,
        quiet=args.quiet,
        dry_run=args.dry_run,
    )
    if args.verbose:
        logging.getLogger("flynt").setLevel(logging.DEBUG)

    if args.string:
        converted, _ = fstringify_code_by_line(
            " ".join(args.src),
            state=state,
        )
        print(converted)
        return 0

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
                f"Supported options are: {supported_args}",
            )
        parser.set_defaults(**cfg)
        args = parser.parse_args(arglist)
    if not args.quiet:
        print(salutation)
    if args.verbose:
        print(f"Using following options: {args}")
    if args.dry_run:
        print("Running flynt in dry-run mode. No files will be changed.")
    return fstringify(
        args.src,
        excluded_files_or_paths=args.exclude,
        fail_on_changes=args.fail_on_change,
        state=state,
    )
