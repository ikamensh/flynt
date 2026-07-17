# Contributor Guide

This repository contains `flynt`, a CLI tool (implemented in Rust since 2.0)
that converts old Python string formatting to f-strings. The Rust code lives
in `src/`, unit/differential tests in `tests/`, the integration harness in
`harness/`, and the golden fixture corpus in `test/integration/`.

## Development Setup
- Stable **Rust** toolchain (rustup) and **uv** for the harness.
- `cargo build` — binary at `target/debug/flynt`.

## Style and Linting
- `cargo fmt` and `cargo clippy` on changed code.
- pre-commit runs `codespell` and a `cargo fmt --check` hook
  (`pre-commit install` to enable).

## Testing
- `cargo test` — unit tests plus differential tests pinned against the Python
  1.x reference implementation (`tests/fixtures/*.json`).
- `uv run --no-project --with pytest pytest harness -q` — the integration
  harness driving the real binary over the golden corpus and the CLI surface.
- Functional changes should include integration tests.

### How integration tests work

All files from `test/integration/samples_in` are processed with `flynt` and
the result is compared byte-for-byte with `test/integration/expected_out`
(same file name; variants `_single_line`, `_concat`, `_enable_*`). It is
enough to add a file in samples_in and expected_out — the harness picks them
up automatically. Sometimes we check for no changes to be done; then the
samples_in version is the same as expected_out.

## Notes
- `cargo test`, the harness, and `pre-commit` should pass before sending a PR.
- If you change CLI flags, update `print_help` in `src/cli.rs` and run
  `python update_readme.py` to put the latest help output into the readme.
- Behavior parity with flynt 1.x is the contract; intentional differences are
  documented in `DIVERGENCES.md`.
