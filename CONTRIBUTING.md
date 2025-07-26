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

You can see existing tests in folder `test/integration`. All files from `samples_in` folder will be processed with `flynt`,
transformed, and result is compared with `expected_out`. Files are matched by name, i.e. transformed version of samples_in/file.py
should exactly match expected_out/file.py. Sometimes we check for no changes to be done, then sample_in version is the same as expected_out.


## CLI tests

When contributing CLI changes, please include a CLI test to verify they are parsed correctly.
`test_cli.py` tests via `run_flynt_cli` function.
