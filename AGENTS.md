# Contributor Guide

This repository contains `flynt`, a Python package that converts old string formatting to f-strings. The code lives in `src/` and tests in `test/`.

## Development Setup
- Use **Python 3.8+**.
- Install dependencies in editable mode: `pip install -e .[dev]`.
- Install pre-commit hooks with `pre-commit install`.

## Style and Linting
- The project uses **pre-commit** with `ruff-format`, `ruff`, `codespell`, and `mypy`.
- Run `pre-commit run --files <file1> <file2>` on changed files (or `pre-commit run -a` for all) before committing.
- You can run the lint checks directly with `ruff check .`.

## Testing
- Execute the full test suite with `pytest`.
- Functional changes should include both unit tests and integration tests.
- Place integration tests under `test/integration/`. CLI-related tests live in `test/test_cli.py`.

### How integration tests work
You can see existing tests in folder `test/integration`. Very high level description is that `conftest.py` lists files to try,
and then they read from `samples_in` folder, transformed, and result is compared with `expected_out`.
Output is also written for manual inspection to `actual_out` folder. There are multiple `expected_out`
folders depending on what mode is used (single line, string concat). `test_files.py` tests via `fstringify_code_by_line` function call,
which includes all processing steps except for CLI parsing and messages.

## Notes
- `pytest` and `pre-commit` should pass before sending a PR.
