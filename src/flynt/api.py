import ast
import os
import sys
import time
import traceback
from typing import Tuple, List
from difflib import unified_diff

import astor

from flynt import state
from flynt.cli_messages import farewell_message
from flynt.process import fstringify_code_by_line, fstringify_concats

blacklist = {".tox", "venv", "site-packages", ".eggs"}


def _fstringify_file(
    filename, multiline, len_limit, transform_concat=False
) -> Tuple[bool, int, int, int]:
    """
    :return: tuple: (changes_made, n_changes,
    length of original code, length of new code)
    """

    with open(filename, encoding="utf-8") as f:
        contents = f.read()

    def default_result():
        return False, 0, len(contents), len(contents)

    try:
        ast_before = ast.parse(contents)
    except SyntaxError:
        if not state.quiet:
            print(f"Can't parse {filename} as a python file.")
        return default_result()

    try:
        new_code, changes = fstringify_code_by_line(
            contents, multiline=multiline, len_limit=len_limit
        )
        if transform_concat:
            new_code, concat_changes = fstringify_concats(
                new_code, multiline=multiline, len_limit=len_limit
            )
            changes += concat_changes
            state.concat_changes += concat_changes

    except Exception as e:
        if not state.quiet:
            if str(e):
                msg = str(e)
            else:
                msg = e.__class__.__name__
            print(f"Skipping fstrings transform of file {filename} due to {msg}.")
            if state.verbose:
                traceback.print_exc()

        return default_result()

    if new_code == contents:
        return default_result()

    try:
        ast_after = ast.parse(new_code)
    except SyntaxError:
        print(f"Faulty result during conversion on {filename} - skipping.")
        if state.verbose:
            print(new_code)
            traceback.print_exc()
        return default_result()

    if not len(ast_before.body) == len(ast_after.body):
        print(
            f"Faulty result during conversion on {filename}: "
            f"statement count has changed, which is not intended - skipping."
        )
        return default_result()

    if state.dry_run:
        for l in unified_diff(contents.split('\n'), new_code.split('\n'), fromfile=filename):
            print(l)
    else:
        with open(filename, "w", encoding="utf-8", newline="") as f:
            f.write(new_code)

    return True, changes, len(contents), len(new_code)


def fstringify_files(files, multiline, len_limit, transform_concat):
    changed_files = 0
    total_charcount_original = 0
    total_charcount_new = 0
    total_expressions = 0
    start_time = time.time()
    for path in files:
        changed, count_expressions, charcount_original, charcount_new = _fstringify_file(
            path, multiline, len_limit, transform_concat
        )
        if changed:
            changed_files += 1
            total_expressions += count_expressions
        total_charcount_original += charcount_original
        total_charcount_new += charcount_new

        if state.verbose:
            status = "modified" if count_expressions else "no change"
            print(f"fstringifying {path}...{status}")
    total_time = time.time() - start_time

    if not state.quiet:
        _print_report(
            changed_files,
            total_charcount_new,
            total_charcount_original,
            total_expressions,
            total_time,
        )

    return changed_files


def _print_report(
    changed_files, total_cc_new, total_cc_original, total_expr, total_time
):
    print("\nFlynt run has finished. Stats:")
    print(f"\nExecution time:                            {total_time:.3f}s")
    print(f"Files modified:                            {changed_files}")
    if changed_files:
        cc_reduction = total_cc_original - total_cc_new
        cc_percent_reduction = cc_reduction / total_cc_original
        print(
            f"Character count reduction:                 {cc_reduction} ({cc_percent_reduction:.2%})\n"
        )

        print("Per expression type:")
        if state.percent_candidates:
            percent_fraction = state.percent_transforms / state.percent_candidates
            print(
                f"Old style (`%`) expressions attempted:     {state.percent_transforms}/"
                f"{state.percent_candidates} ({percent_fraction:.1%})"
            )
        else:
            print("No old style (`%`) expressions attempted.")

        if state.call_candidates:
            print(
                f"`.format(...)` calls attempted:            {state.call_transforms}/"
                f"{state.call_candidates} ({state.call_transforms / state.call_candidates:.1%})"
            )
        else:
            print("No `.format(...)` calls attempted.")

        if state.concat_candidates:
            print(
                f"String concatenations attempted:           {state.concat_changes}/"
                f"{state.concat_candidates} ({state.concat_changes / state.concat_candidates:.1%})"
            )
        else:
            print("No concatenations attempted.")

        print(f"F-string expressions created:              {total_expr}")

        if state.invalid_conversions:
            print(
                f"Out of all attempted transforms, {state.invalid_conversions} resulted in errors."
            )
            print("To find out specific error messages, use --verbose flag.")

    print("\n" + ("_-_." * 25))
    print(farewell_message)


def fstringify(
    files_or_paths,
    multiline,
    len_limit,
    fail_on_changes=False,
    transform_concat=False,
    excluded_files_or_paths=None,
):
    """ determine if a directory or a single file was passed, and f-stringify it."""

    files = _resolve_files(files_or_paths, excluded_files_or_paths)

    status = fstringify_files(
        files,
        multiline=multiline,
        len_limit=len_limit,
        transform_concat=transform_concat,
    )

    if fail_on_changes:
        return status
    else:
        return 0


def _resolve_files(files_or_paths, excluded_files_or_paths) -> List[str]:
    """Resolve relative paths and directory names into a list of absolute paths to python files."""

    files = []
    _blacklist = blacklist.copy()
    if excluded_files_or_paths is not None:
        _blacklist.update(set(excluded_files_or_paths))

    for file_or_path in files_or_paths:

        abs_path = os.path.abspath(file_or_path)

        if not os.path.exists(abs_path):
            print(f"`{file_or_path}` not found")
            sys.exit(1)

        if os.path.isdir(abs_path):
            for folder, filename in astor.code_to_ast.find_py_files(abs_path):
                files.append(os.path.join(folder, filename))
        else:
            files.append(abs_path)

    files = [f for f in files if all(b not in f for b in _blacklist)]
    return files
