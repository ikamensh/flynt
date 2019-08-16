import os
import sys
import time
import traceback
from typing import Tuple

import astor
import pyupgrade

from flynt.file_spy import spy_on_file_io, charcount_stats
from flynt.process import fstringify_code_by_line
from flynt.cli_messages import message_pyup_success, message_suggest_pyup, farewell_message

blacklist = {".tox", "venv", "site-packages", ".eggs"}


def fstringify_file(
    filename, multiline, len_limit, pyup=False
) -> Tuple[bool, int, int, int]:
    """
    :return: tuple: (changes_made, n_changes, length of original code, length of new code)
    """

    try:
        with open(filename, encoding="utf-8") as f:
            contents = f.read()

        new_code, changes = fstringify_code_by_line(
            contents, multiline=multiline, len_limit=len_limit
        )

    except Exception as e:
        print(f"Skipping fstrings transform of file {filename} due to {e}")
        traceback.print_exc()
        result = False, 0, len(contents), len(contents)
    else:
        if new_code == contents:
            result = False, 0, len(contents), len(contents)
        else:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(new_code)

            result = True, changes, len(contents), len(new_code)

    if not pyup:
        return result
    else:

        class Args:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        args = Args(
            py36_plus=True,
            py3_plus=True,
            keep_percent_format=False,
            exit_zero_even_if_changed=False,
        )

        with spy_on_file_io():
            changed = pyupgrade.fix_file(filename, args)

        if changed:
            len_before, len_after = charcount_stats(filename)
            return True, result[1], result[2], len_after
        else:
            return result


def fstringify_files(files, verbose, quiet, multiline, len_limit, pyup):
    changed_files = 0
    total_charcount_original = 0
    total_charcount_new = 0
    total_expressions = 0
    start_time = time.time()
    for f in files:
        if any(b in f[0] for b in blacklist):
            continue
        file_path = os.path.join(f[0], f[1])
        changed, count_expressions, charcount_original, charcount_new = fstringify_file(
            file_path, multiline, len_limit, pyup
        )
        if changed:
            changed_files += 1
            total_expressions += count_expressions
        total_charcount_original += charcount_original
        total_charcount_new += charcount_new
        status = "yes" if count_expressions else "no"

        if verbose and not quiet:
            print(f"fstringifying {file_path}...{status}")
    total_time = round(time.time() - start_time, 3)

    if not quiet:
        print_report(changed_files, pyup, total_charcount_new, total_charcount_original,
                     total_expressions, total_time)

    return changed_files


def print_report(changed_files, pyup, total_cc_new, total_cc_original, total_expr, total_time):
    print("\nFlynt run has finished. Stats:")
    print(f"\nExecution time: {total_time}s")
    print(f"Files modified: {changed_files}")
    print(f"String expressions transformed: {total_expr}")
    cc_reduction = total_cc_original - total_cc_new
    cc_percent_reduction = cc_reduction / total_cc_original
    print(f"Character count reduction: {cc_reduction} ({cc_percent_reduction:.2%})\n")
    print("_-_." * 25)
    if not pyup:
        print(message_suggest_pyup)
    else:
        print(message_pyup_success)
    print(farewell_message)
    print("_-_." * 25)


def fstringify(
    files_or_paths, verbose, quiet, multiline, len_limit, pyup, fail_on_changes=False
):
    """ determine if a directory or a single file was passed, and f-stringify it."""

    files = []

    for file_or_path in files_or_paths:
        abs_path = os.path.abspath(file_or_path)

        if not os.path.exists(abs_path):
            print(f"`{file_or_path}` not found")
            sys.exit(1)

        if os.path.isdir(abs_path):
            files.extend(astor.code_to_ast.find_py_files(abs_path))
        else:
            files.append((os.path.dirname(abs_path), os.path.basename(abs_path)))

    status = fstringify_files(
        files,
        verbose=verbose,
        quiet=quiet,
        multiline=multiline,
        len_limit=len_limit,
        pyup=pyup,
    )

    if fail_on_changes:
        return status
    else:
        return 0
