# Flynt Architecture Overview

This document provides a short overview of the main modules that make up Flynt
and how they interact. It is intended to help new contributors find their way
around the codebase.

## Entry points

Flynt exposes a command line interface (CLI) and a small API:

- **`src/flynt/__main__.py`** – the `python -m flynt` entry point. It simply
  calls `flynt.main()`.
- **`src/flynt/cli.py`** – parses command line arguments and eventually invokes
  `flynt.api.fstringify` with a configured `State` object.
- **`src/flynt/api.py`** – high level API used by the CLI and tests. It contains
  `fstringify_code` (convert a string), `fstringify_files` (convert multiple
  files) and `fstringify` (resolve paths and run the conversion).

## State and configuration

`src/flynt/state.py` defines the `State` dataclass. It stores command line
options (e.g. `--aggressive`, `--line-length`) as well as counters used for the
final conversion report. CLI arguments and optional `pyproject.toml` values are
translated into a `State` instance in `cli.py`.

Configuration is loaded from a `pyproject.toml` (found via
`find_pyproject_toml` in `src/flynt/utils/pyproject_finder.py`). CLI options
override configuration file values.

## Code transformation pipeline

For each file, Flynt executes the following steps (implemented mainly in
`flynt.api` and `flynt.code_editor`):

1. **Candidate discovery** – Code is parsed into an AST and inspected for
   formatting operations that can be transformed. Modules under
   `src/flynt/candidates/` find:
   - old style `%` formatting (`ast_percent_candidates.py`)
   - `.format()` calls (`ast_call_candidates.py`)
   Candidates are represented by `AstChunk` objects which store start and end
   positions inside the source code.
2. **Optional candidate providers** – Additional transformations are available
   for string concatenations (`src/flynt/string_concat/`) and static
   `.join()` calls (`src/flynt/static_join/`). These are enabled through CLI
   options and use the same `AstChunk` abstraction.
3. **Editing** – `src/flynt/code_editor.py` orchestrates the process. It keeps
   the original source lines and walks through the sorted list of candidates.
   For each candidate it calls a transform function and, if the result fits the
   current line length constraints, replaces the original code while keeping the
   rest of the file untouched. The transform function also increments the
   counters in `State`.
4. **AST based transformation** – The actual conversion logic lives in
   `src/flynt/transform/`. The central function `transform_chunk` calls
   `fstringify_node` from `FstringifyTransformer.py` which applies two
   transformations:
   - `percent_transformer.py` converts `%` based formatting.
   - `format_call_transforms.py` converts `.format()` calls.
   These operate on the AST and return an `ast.JoinedStr` representing the new
   f-string. After transformation, helper functions in `flynt.utils.utils`
   format the result back into source code with consistent quoting.

## Utilities

- `src/flynt/utils/format.py` contains helper logic for detecting and modifying
  string quoting.
- `src/flynt/utils/utils.py` provides AST helpers such as `ast_to_string`,
  `ast_formatted_value`, and the `str_in_str` detection used to avoid unsafe
  conversions.
- `src/flynt/linting/fstr_lint.py` contains utilities used by the
  transformation pipeline to inline nested f-strings and to detect existing
  f-strings.

## Tests

Unit and integration tests live in `test/`. The integration suite in
`test/integration/` feeds example files through the public API and verifies the
exact output. Tests are executed with `pytest` and formatting is enforced via
`pre-commit` hooks.
