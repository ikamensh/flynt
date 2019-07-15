__version__ = "0.17"

import argparse
import sys

from flynt.api import fstringify_dir, fstringify_file, fstringify
from flynt.transform import transform_chunk
from flynt.process import fstringify_code_by_line


def main():
    parser = argparse.ArgumentParser(
        description=f"flynt {__version__}", add_help=True
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--verbose", action="store_true", help="run with verbose output",
                       default=True)
    group.add_argument("--quiet", action="store_true", help="run without output",
                       default=False)
    parser.add_argument(
        "--version", action="store_true", default=False, help="show version and exit"
    )
    parser.add_argument("src", action="store", help="source file or directory")

    args = parser.parse_args()

    if args.version:
        print("flynt", __version__)
        sys.exit(0)

    fstringify(args.src, verbose=args.verbose, quiet=args.quiet)


if __name__ == "__main__":
    main()
