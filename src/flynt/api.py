import os
import sys
import time
import traceback
from typing import Tuple

import astor

from flynt.process import fstringify_code_by_line

blacklist = {'.tox', 'venv', 'site-packages', '.eggs'}

def fstringify_file(filename, multiline, len_limit) -> Tuple[int, int, int]:
    """
    :param filename:
    :return: tuple: (n_changes, length of original code,
    length of new code)
    """

    try:
        with open(filename, encoding='utf-8') as f:
            contents = f.read()

        new_code, changes = fstringify_code_by_line(contents,
                                                    transform_multiline=multiline,
                                                    len_limit=len_limit)
    except Exception as e:
        print(f"Skipping file {filename} due to {e}")
        traceback.print_exc()
        return 0, len(contents), len(contents)
    else:
        if new_code == contents:
            return 0, len(contents), len(contents)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(new_code)

        return changes, len(contents), len(new_code)

def fstringify_files(files, verbose, quiet, multiline, len_limit):
    changed_files = 0
    total_charcount_original = 0
    total_charcount_new = 0
    total_expressions = 0
    start_time = time.time()
    for f in files:
        if any(b in f[0] for b in blacklist):
            continue
        file_path = os.path.join(f[0], f[1])
        count_expressions, charcount_original, charcount_new = fstringify_file(file_path,
                                                                               multiline,
                                                                               len_limit)
        if count_expressions:
            changed_files += 1
            total_expressions += count_expressions
        total_charcount_original += charcount_original
        total_charcount_new += charcount_new
        status = "yes" if count_expressions else "no"

        if verbose and not quiet:
            print(f"fstringifying {file_path}...{status}")

    total_time = round(time.time() - start_time, 3)

    if not quiet:
        print("\nFlynt run has finished. Stats:")

        print(f"\nExecution time: {total_time}s")
        print(f"Files modified: {changed_files}")
        print(f"Expressions transformed: {total_expressions}")
        cc_reduction = total_charcount_original - total_charcount_new
        charcount_percent_reduction =  cc_reduction / total_charcount_original
        print(f"Character count reduction: {cc_reduction} ({charcount_percent_reduction:.2%})\n")
        print('_-_.'*25)
        print("\nPlease run your tests before commiting. Report bugs as github issues at: https://github.com/ikamensh/flynt")
        print("Thank you for using flynt! Fstringify more projects and recommend it to your colleagues!\n")
        print('_-_.'*25)


def fstringify(file_or_path, verbose, quiet, multiline, len_limit):
    """ determine if a directory or a single file was passed, and f-stringify it."""
    abs_path = os.path.abspath(file_or_path)

    if not os.path.exists(abs_path):
        print(f"`{file_or_path}` not found")
        sys.exit(1)

    if os.path.isdir(abs_path):
        files = astor.code_to_ast.find_py_files(abs_path)
    else:
        files = ((os.path.dirname(abs_path), os.path.basename(abs_path)),)

    fstringify_files(files, verbose=verbose, quiet=quiet, multiline=multiline, len_limit=len_limit)
