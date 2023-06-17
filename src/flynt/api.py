import ast
import codecs
import dataclasses
import logging
import os
import sys
import time
import traceback
from difflib import unified_diff
from typing import Collection, List, Optional, Tuple

import astor

from flynt.code_editor import (
    fstringify_code_by_line,
    fstringify_concats,
    fstringify_static_joins,
)
from flynt.state import State

log = logging.getLogger(__name__)

blacklist = {".tox", "venv", "site-packages", ".eggs"}


@dataclasses.dataclass(frozen=True)
class FstringifyResult:
    n_changes: int
    original_length: int
    new_length: int
    content: str


def _fstringify_file(
    filename: str,
    state: State,
) -> Optional[FstringifyResult]:
    """
    F-stringify a file, write changes, and return a change result.
    """
    encoding, bom = encoding_by_bom(filename)

    with open(filename, encoding=encoding, newline="") as f:
        try:
            contents = f.read()
        except UnicodeDecodeError:
            log.error(f"Exception while reading {filename}", exc_info=True)
            return None

    result = fstringify_code(
        contents=contents,
        state=state,
        filename=filename,
    )

    if result is None:
        return None

    new_code = result.content
    if state.dry_run and result.n_changes:
        diff = unified_diff(
            contents.split("\n"),
            new_code.split("\n"),
            fromfile=filename,
        )
        print("\n".join(diff))
    elif state.stdout:
        print(new_code)
    elif result.n_changes:
        with open(filename, "wb") as outf:
            if bom is not None:
                outf.write(bom)
            outf.write(new_code.encode(encoding))
    return result


def fstringify_code(
    contents: str,
    state: State,
    filename: str = "<code>",
) -> Optional[FstringifyResult]:
    """transform given string, assuming it's python code."""
    try:
        ast_before = ast.parse(contents)
    except SyntaxError:
        log.exception(f"Can't parse {filename} as a python file.")
        return None

    try:
        new_code = contents
        changes = 0
        if state.transform_percent or state.transform_format:
            new_code, changes = fstringify_code_by_line(
                contents,
                state=state,
            )
        if state.transform_concat:
            try:
                new_code, concat_changes = fstringify_concats(
                    new_code,
                    state=state,
                )
            except Exception:
                msg = traceback.format_exc()
                log.error("Transforming concatenation of literal strings failed")
                log.error(msg)
            else:
                changes += concat_changes
                state.concat_changes += concat_changes
        if state.transform_join:
            try:
                new_code, join_changes = fstringify_static_joins(
                    new_code,
                    state=state,
                )
            except Exception:
                msg = traceback.format_exc()
                log.error("Transforming concatenation of literal strings failed")
                log.error(msg)
            else:
                changes += join_changes
                state.join_changes += join_changes

    except Exception as e:
        msg = str(e) or e.__class__.__name__
        log.warning(
            f"Skipping fstrings transform of file {filename} due to {msg}.",
            exc_info=True,
        )
        return None

    result = FstringifyResult(
        n_changes=changes,
        original_length=len(contents),
        new_length=len(new_code),
        content=new_code,
    )

    if result.content == contents:
        return result

    try:
        ast_after = ast.parse(new_code)
    except SyntaxError:
        log.warning(
            f"Faulty result during conversion on {filename} - skipping.",
            exc_info=True,
        )
        return None

    if not len(ast_before.body) == len(ast_after.body):
        log.error(
            f"Faulty result during conversion on {filename}: "
            f"statement count has changed, which is not intended - skipping.",
        )
        return None
    return result


def fstringify_files(
    files: List[str],
    state: State,
) -> int:
    """apply transforms to sequence of files, keep shared stats."""
    changed_files = 0
    total_charcount_original = 0
    total_charcount_new = 0
    total_expressions = 0
    start_time = time.time()
    for path in files:
        result = _fstringify_file(
            path,
            state,
        )
        if result:
            if result.n_changes:
                changed_files += 1
                total_expressions += result.n_changes
            total_charcount_original += result.original_length
            total_charcount_new += result.n_changes
            status = "modified" if result.n_changes else "no change"
        else:
            status = "failed"
        log.info(f"fstringifying {path}...{status}")
    total_time = time.time() - start_time

    if not state.quiet:
        _print_report(
            state,
            len(files),
            changed_files,
            total_charcount_new,
            total_charcount_original,
            total_expressions,
            total_time,
        )

    return changed_files


farewell_message = (
    "Please run your tests before committing. Did flynt get a perfect conversion? give it a star at: "
    "\n~ https://github.com/ikamensh/flynt ~"
    "\nThank you for using flynt. Upgrade more projects and recommend it to your colleagues!\n"
)


def _print_report(
    state: State,
    found_files: int,
    changed_files: int,
    total_cc_new: int,
    total_cc_original: int,
    total_expr: int,
    total_time: float,
) -> None:
    print("\nFlynt run has finished. Stats:")
    print(f"\nExecution time:                            {total_time:.3f}s")
    print(f"Files checked:                             {found_files}")
    print(f"Files modified:                            {changed_files}")
    if changed_files:
        cc_reduction = total_cc_original - total_cc_new
        cc_percent_reduction = cc_reduction / total_cc_original
        print(
            f"Character count reduction:                 {cc_reduction} ({cc_percent_reduction:.2%})\n",
        )

        print("Per expression type:")
        if state.percent_candidates:
            percent_fraction = state.percent_transforms / state.percent_candidates
            print(
                f"Old style (`%`) expressions attempted:     {state.percent_transforms}/"
                f"{state.percent_candidates} ({percent_fraction:.1%})",
            )
        else:
            print("No old style (`%`) expressions attempted.")

        if state.call_candidates:
            print(
                f"`.format(...)` calls attempted:            {state.call_transforms}/"
                f"{state.call_candidates} ({state.call_transforms / state.call_candidates:.1%})",
            )
        else:
            print("No `.format(...)` calls attempted.")

        if state.concat_candidates:
            print(
                f"String concatenations attempted:           {state.concat_changes}/"
                f"{state.concat_candidates} ({state.concat_changes / state.concat_candidates:.1%})",
            )
        else:
            print("No concatenations attempted.")

        if state.join_candidates:
            print(
                f"Static string joins attempted:             {state.join_changes}/"
                f"{state.join_candidates} ({state.join_changes / state.join_candidates:.1%})",
            )
        else:
            print("No static string joins attempted.")

        print(f"F-string expressions created:              {total_expr}")

        if state.invalid_conversions:
            print(
                f"Out of all attempted transforms, {state.invalid_conversions} resulted in errors.",
            )
            print("To find out specific error messages, use --verbose flag.")

    print(f"\n{'_-_.' * 25}")
    print(farewell_message)


def fstringify(
    files_or_paths: List[str],
    state: State,
    fail_on_changes: bool = False,
    excluded_files_or_paths: Optional[Collection[str]] = None,
) -> int:
    """determine if a directory or a single file was passed, and f-stringify it."""
    files = _resolve_files(files_or_paths, excluded_files_or_paths)

    status = fstringify_files(
        files,
        state=state,
    )

    if fail_on_changes:
        return status
    return 0


def _resolve_files(
    files_or_paths: List[str],
    excluded_files_or_paths: Optional[Collection[str]],
) -> List[str]:
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


def encoding_by_bom(path: str, default: str = "utf-8") -> Tuple[str, Optional[bytes]]:
    """Adapted from https://stackoverflow.com/questions/13590749/reading-unicode-file-data-with-bom-chars-in-python/24370596#24370596"""
    with open(path, "rb") as f:
        raw = f.read(4)  # will read less if the file is smaller
    # BOM_UTF32_LE's start is equal to BOM_UTF16_LE so need to try the former first
    for enc, boms in (
        ("utf-8-sig", (codecs.BOM_UTF8,)),
        ("utf-32", (codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)),
        ("utf-16", (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)),
    ):
        for bom in boms:
            if raw.startswith(bom):
                return enc, bom
    return default, None
