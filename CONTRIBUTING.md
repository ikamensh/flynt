# Development setup

flynt 2.x is implemented in Rust. You need a stable Rust toolchain
(https://rustup.rs) and, for the integration harness, `uv`
(https://docs.astral.sh/uv/).

```
cargo build            # binary at target/debug/flynt
cargo test             # unit + differential tests
uv run --no-project --with pytest pytest harness -q   # integration harness
```

# Code style

`cargo fmt` and `cargo clippy` before committing. pre-commit runs codespell.

# Integration tests

**When contributing any new functionality, please include appropriate
integration tests.**

By integration test we mean taking a whole file, running the high level
transform on it, and checking for exactly the expected output.

## How integration tests work

The golden corpus lives in `test/integration`: every file from `samples_in` is
converted and compared byte-for-byte with the file of the same name in
`expected_out` (plus the `_single_line`, `_concat`, and `_enable_*` variants).
It's enough to add a file to `samples_in` and `expected_out`; the harness
(`harness/test_golden.py`) picks it up automatically. Sometimes we check that
no changes are made — then the sample equals the expected output.

## CLI tests

When contributing CLI changes, add a case to `harness/test_cli_binary.py`,
which runs the real binary via subprocess.

## Differential tests against flynt 1.x

`tests/fixtures/*.json` pin the exact behavior of the Python reference
implementation, consumed by `tests/*_differential.rs`. To regenerate them you
need a venv with the last Python flynt (see the header comments in
`tests/fixtures/gen_*.py`).
