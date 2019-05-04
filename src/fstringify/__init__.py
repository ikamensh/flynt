__version__ = "0.1.5"


import argparse
import sys

from fstringify.api import fstringify_dir, fstringify_file, fstringify
from fstringify.transform import fstringify_code
from fstringify.process import fstringify_code_by_line


def main():
    parser = argparse.ArgumentParser(
        description=f"fstringify {__version__}", add_help=True
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verbose", action="store_true", help="run with verbose output")
    group.add_argument("--quiet", action="store_true", help="run without output")
    parser.add_argument(
        "--version", action="store_true", default=False, help="show version and exit"
    )
    parser.add_argument("src", action="store", help="source file or directory")

    args = parser.parse_args()

    if args.version:
        print("fstringify", __version__)
        sys.exit(0)

    fstringify(args.src, verbose=args.verbose, quiet=args.quiet)


if __name__ == "__main__":
    main()
