import os
import sys
import time
import traceback
from typing import Tuple

import astor

from flynt.process import fstringify_code_by_line

blacklist = {'.tox', 'venv', 'site-packages', '.eggs'}

def fstringify_file(filename) -> Tuple[bool, int, int]:
    """
    :param filename:
    :return: tuple: (if the file was edited, length of original code, length of new code)
    """

    try:
        with open(filename, encoding='utf-8') as f:
            contents = f.read()

        new_code, changes = fstringify_code_by_line(contents)
    except Exception as e:
        print(f"Skipping file {filename} due to {e}")
        traceback.print_exc()
        return False, len(contents), len(contents)
    else:
        if new_code == contents:
            return False, len(contents), len(contents)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(new_code)

        return True, len(contents), len(new_code)


def fstringify_dir(in_dir):
    files = astor.code_to_ast.find_py_files(in_dir)
    return fstringify_files(files)


def fstringify_files(files, verbose=False, quiet=False):
    change_count = 0
    total_charcount_original = 0
    total_charcount_new = 0
    start_time = time.time()
    for f in files:
        if any(b in f[0] for b in blacklist):
            continue
        file_path = os.path.join(f[0], f[1])
        changed, charcount_original, charcount_new = fstringify_file(file_path)
        if changed:
            change_count += 1
        total_charcount_original += charcount_original
        total_charcount_new += charcount_new
        status = "yes" if changed else "no"

        if verbose and not quiet:
            print(f"fstringifying {file_path}...{status}")

    total_time = round(time.time() - start_time, 3)

    if not quiet:
        file_s = "s" if change_count != 1 else ""
        print(f"\nfstringified {change_count} file{file_s} in {total_time}s")
        charcount_percent_reduction = 100 *(total_charcount_original - total_charcount_new) / total_charcount_original
        print(f"character count in python source files was reduced by {charcount_percent_reduction:.2f}%")


def fstringify(file_or_path, verbose=False, quiet=False):
    """ determine if a directory or a single file was passed, and f-stringify it."""
    abs_path = os.path.abspath(file_or_path)
    if not os.path.exists(abs_path):
        print(f"`{file_or_path}` not found")
        sys.exit(1)

    if os.path.isdir(abs_path):
        files = astor.code_to_ast.find_py_files(abs_path)
    else:
        files = ((os.path.dirname(abs_path), os.path.basename(abs_path)),)

    fstringify_files(files, verbose=verbose, quiet=quiet)
