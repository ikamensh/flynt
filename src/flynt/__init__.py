""" `flynt` is a command line tool to automatically convert a project's Python code
from old "%-formatted" and .format(...) strings into Python 3.6+'s f-strings.
Learn more about f-strings at https://www.python.org/dev/peps/pep-0498/"""

__version__ = "0.27"

import argparse
import sys

from flynt.api import fstringify

def main():
    parser = argparse.ArgumentParser(
        description=f"flynt v.{__version__}", add_help=True, epilog=__doc__
    )

    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument("--verbose", action="store_true", help="run with verbose output",
                       default=False)
    verbosity_group.add_argument("--quiet", action="store_true", help="run without output",
                       default=False)

    multiline_group = parser.add_mutually_exclusive_group()
    multiline_group.add_argument("--no_multiline",
                       action="store_true",
                       help="convert only single line expressions",
                       default=False)

    multiline_group.add_argument("--line_length",
                       action="store",
                       help="for expressions spanning multiple lines, convert only if "
                            "the resulting single line will fit into the line length limit. "
                            "Default value is 79 characters.",
                       default=79)

    parser.add_argument(
        "--upgrade", action="store_true", default=False, help="run pyupgrade on .py files"
    )

    parser.add_argument("--fail-on-change", action="store_true", default=False, help="Fail when changing files (for linting purposes)")
    parser.add_argument("src", action="store", nargs="+", help="source file(s) or directory")

    args = parser.parse_args()

    return fstringify(args.src,
                      verbose = args.verbose,
                      quiet = args.quiet,
                      multiline = not args.no_multiline,
                      len_limit = int(args.line_length),
                      pyup = args.upgrade,
                      fail_on_changes=args.fail_on_change)


if __name__ == "__main__":
    sys.exit(main())
