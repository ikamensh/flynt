"""This module parses the command line arguments and passes them to flynt.api.fstringify."""

import argparse
import sys

from flynt.api import fstringify
from flynt import state
from flynt import __version__


def main():
    print(f"Running flynt v.{__version__}")
    parser = argparse.ArgumentParser(
        description=f"flynt v.{__version__}", add_help=True, epilog=__doc__
    )

    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        "--verbose", action="store_true", help="run with verbose output", default=False
    )
    verbosity_group.add_argument(
        "--quiet", action="store_true", help="run without output", default=False
    )

    multiline_group = parser.add_mutually_exclusive_group()
    multiline_group.add_argument(
        "--no_multiline", action="store_true", help=argparse.SUPPRESS, default=False
    )

    multiline_group.add_argument(
        "--no-multiline",
        action="store_true",
        help="convert only single line expressions",
        default=False,
    )

    multiline_group.add_argument(
        "--line_length", action="store", help=argparse.SUPPRESS, default=88
    )

    multiline_group.add_argument(
        "--line-length",
        action="store",
        help="for expressions spanning multiple lines, convert only if "
        "the resulting single line will fit into the line length limit. "
        "Default value is 88 characters.",
        default=88,
    )

    parser.add_argument(
        "--transform-concats",
        action="store_true",
        default=False,
        help="Replace string concatenations (defined as + operations involving string literals) "
        "with f-strings. Available only if flynt is installed with 3.8+ interpreter.",
    )

    parser.add_argument(
        "--fail-on-change",
        action="store_true",
        default=False,
        help="Fail when changing files (for linting purposes)",
    )
    parser.add_argument(
        "src", action="store", nargs="+", help="source file(s) or directory"
    )

    args = parser.parse_args()

    if args.transform_concats:
        if sys.version_info < (3, 8):
            raise Exception(
                f"""Transforming string concatenations is only possible with flynt 
                installed to a python3.8+ interpreter. Currently using {sys.version_info}."""
            )

    state.verbose = args.verbose
    state.quiet = args.quiet

    return fstringify(
        args.src,
        multiline=not args.no_multiline,
        len_limit=int(args.line_length),
        fail_on_changes=args.fail_on_change,
        transform_concat=args.transform_concats,
    )
