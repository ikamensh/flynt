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

You can see existing tests in folder `test/integration`. All files from `test/integration/samples_in` folder will be processed with `flynt`,
transformed, and result is compared with `test/integration/expected_out`.
Files are matched by name, i.e. transformed version of samples_in/file.py
should exactly match expected_out/file.py. Its enough to add a file in samples_in and expected_out, they will
be picked up automatically by finding all files in the folder.
Sometimes we check for no changes to be done, then sample_in version is the same as expected_out.

## Notes
- `pytest` and `pre-commit` should pass before sending a PR.
- If you change CLI flags, run `python update_readme.py` to put latest help output into readme.
