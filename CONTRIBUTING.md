# Running tests
In order for imports to work, install package in editable mode in your environment with `pip install -e .[dev]`.

# Code style
[pre-commit](https://github.com/pre-commit/pre-commit) is used, to run code checks before committing changes.

If you have pre-commit installed (e.g. from the dev requirements), simply run ``pre-commit install`` to install the hooks for this repo.

# Integration tests

**When contributing any new functionality, please include appropriate integration tests.**

This project relies heavily on tests, as otherwise it is full of hacks (unfortunately).
By integration test we mean taking a whole file, reading it and running high level transform function on it,
then checking for exactly the expected output. 

## How integration tests work

You can see existing tests in folder `test/integration`. Very high level description is that `conftest.py` lists files to try,
and then they read from `samples_in` folder, transformed, and result is compared with `expected_out`.
Output is also written for manual inspection to `actual_out` folder. There are multiple `expected_out`
folders depending on what mode is used (single line, string concat). `test_files.py` tests via `fstringify_code_by_line` function call, 
which includes all processing steps except for CLI parsing and messages.


## CLI tests

When contributing CLI changes, please include a CLI test to verify they are parsed correctly.
`test_cli.py` tests via `run_flynt_cli` function.
