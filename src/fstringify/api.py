import os
import sys
import time

import astor

from fstringify.process import skip_file, fstringify_code_by_line


def fstringify_file(fn):
    if skip_file(fn):
        return False

    with open(fn) as f:
        contents = f.read()

    new_code = fstringify_code_by_line(contents)

    if new_code == contents:
        return False

    with open(fn, "w") as f:
        f.write(new_code)

    return True


def fstringify_dir(in_dir):
    files = astor.code_to_ast.find_py_files(in_dir)
    return fstringify_files(files)


def fstringify_files(files, verbose=False, quiet=False):
    change_count = 0
    start_time = time.time()
    for f in files:
        file_path = os.path.join(f[0], f[1])
        changed = fstringify_file(file_path)
        if changed:
            change_count += 1
        status = "yes" if changed else "no"
        # TODO: only if `verbose` is set

        if verbose and not quiet:
            print(f"fstringifying {file_path}...{status}")

    total_time = round(time.time() - start_time, 3)

    if not quiet:
        file_s = "s" if change_count != 1 else ""
        print(f"\nfstringified {change_count} file{file_s} in {total_time}s")


def fstringify(file_or_path, verbose=False, quiet=False):
    """ determine if a directory or a single file was passed, and f-stringify it."""
    to_use = os.path.abspath(file_or_path)
    if not os.path.exists(to_use):
        print(f"`{file_or_path}` not found")
        sys.exit(1)

    if os.path.isdir(to_use):
        files = astor.code_to_ast.find_py_files(to_use)
    else:
        files = ((os.path.dirname(to_use), os.path.basename(to_use)),)

    fstringify_files(files, verbose=verbose, quiet=quiet)
