__version__="0.0.1"

import argparse, sys, io, mimetypes


def read_file(fname:str) -> str:
    mime = mimetypes.guess_type(fname)
    if mime[0] == 'text/x-python':
        with open(fname, 'r') as f:
            contents=f.read()
    return contents
    

def main():
    parser = argparse.ArgumentParser(
        description=f"flint {__version__}", add_help=True
    )

    # group = parser.add_mutually_exclusive_group()
    # group.add_argument("--verbose", action="store_true", help="run with verbose output")
    # group.add_argument("--quiet", action="store_true", help="run without output")
    parser.add_argument(
        "--version", action="store_true", default=False, help="show version and exit"
    )
    parser.add_argument("src", action="store", help="source file or directory")

    args = parser.parse_args()

    if args.version:
        print("flint", __version__)
        sys.exit(0)

    # flint_str(args.src, verbose=args.verbose, quiet=args.quiet)
    print(read_file(args.src))

if __name__ == "__main__":
    main()
