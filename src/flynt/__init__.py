__version__ = "0.17"

import argparse
import sys

from flynt.api import fstringify


def main():
    parser = argparse.ArgumentParser(
        description=f"flynt {__version__}", add_help=True
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verbose", action="store_true", help="run with verbose output",
                       default=False)
    group.add_argument("--quiet", action="store_true", help="run without output",
                       default=False)

    group.add_argument("--no_multiline",
                       action="store_true",
                       help="convert only single line expressions",
                       default=False)

    group.add_argument("--line_length",
                       action="store",
                       help="for expressions spanning multiple lines, convert only if "
                            "the resulting single line will fit into the line length limit",
                       default=79)

    parser.add_argument(
        "--version", action="store_true", default=False, help="show version and exit"
    )
    parser.add_argument("src", action="store", help="source file or directory")

    args = parser.parse_args()

    if args.version:
        print("flynt", __version__)
        sys.exit(0)

    fstringify(args.src,
               verbose = args.verbose,
               quiet = args.quiet,
               multiline = not args.no_multiline,
               len_limit = int(args.line_length) )


if __name__ == "__main__":
    main()
