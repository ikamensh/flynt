# flynt-rs: results

Pure-Rust port of [flynt](https://github.com/ikamensh/flynt) 1.0.6 (Python
f-string converter). Parser/codegen: ruff crates (git dep, tag 0.14.11).
No Python at runtime.

## Completion criteria: original integration tests

The original flynt integration suite was ported to drive the `flynt-rs`
binary directly (harness/):

| Suite | Result |
|---|---|
| Golden files: `test_files.py` (65 samples × multiline/single-line), `test_concat.py` (12), `test_files_len_limit.py`, enables variants | **139 passed, 1 xfailed** |
| `test_cli.py` + `test_api.py` + `test_notebook_file.py` at binary level (32 tests) | **all pass** |
| Rust unit + differential tests (`cargo test`; includes 1002 unparse, 570 fixup, 888 format-call, 282 percent fixtures generated from Python flynt itself) | **155 pass** |

The 1 xfail is `escaped_newline.py` — xfail in the original suite too
(flynt issue #83); behavior mirrored, not worse.

Exclusions mirrored from the original suite's own EXCLUDED set: `bom.py` and
`class.py` (covered instead at binary level / not tested upstream),
`multiline_limit.py` (tested via the concat path, as upstream does).
Monkeypatch-based Python tests (`test_break_safe`, `test_catches_subtle`,
`test_fstringify_files_charcount`, `test_uniform_path`) can't drive a foreign
binary; their behavior contracts are ported as Rust unit tests in `src/api.rs`
via an injectable transform bundle.

Reference baseline: original flynt 1.0.6 on Python 3.13 passes its own suite
419 passed / 1 skipped / 1 xfailed.

## Real-world differential: Django 1.11 (2,400 files)

Running both tools over the full Django 1.11 tree (defaults):

- Both modify **exactly 526 of 2,400 files**.
- **7 files differ**, all in one documented divergence class (redundant
  parentheses omitted inside converted f-strings — see DIVERGENCES.md #2;
  6 cosmetic + 1 knock-on where the 2-chars-shorter output fits the 88-char
  limit). Everything else is byte-identical, including counters and report.

## Extended differential: 3 corpora × 3 flag variants (pre-release)

Before the 2.0.0b1 release, both tools were run over Django 1.11 (2,398
files), rich (213 files, modern 3.8+ syntax), and cpython 3.13 `Lib/`
(2,549 files incl. match statements, PEP 604/695/701 syntax and
intentionally malformed test data), each with defaults, `-a`, and
`-tc -tj`. For every run: file trees compared byte-for-byte, every changed
file re-parsed with CPython 3.13 (`ast.parse`), and flynt-rs re-run to prove
idempotency (second run changes nothing).

- **Every file-level difference falls in a documented DIVERGENCES.md class**
  (redundant parens #2, `%c` refusal, nested-spec conversions #5, 1.x
  whole-file bail-out #6). No parse failures, no idempotency failures.
- This sweep caught one real bug before release: ruff 0.14.11's `walk_stmt`
  visits `elif` condition expressions twice, so candidates there were
  converted twice (`elif f"{opt}="f"{opt}=" in ...` on `Lib/getopt.py`).
  Fixed by same-range dedup in `chunk::sort_dedup`; regression-tested for
  all four pipelines in `harness/test_elif_dedup.py`.
- A 24-case CLI parity matrix (exit codes, stdout/stderr, tree effects for
  help/version/errors/stdin/config/notebook/etc.) matches 1.0.6 modulo
  documented cosmetics; notebook JSON output is byte-identical (indent=1).

## Speedup (hyperfine, Apple Silicon)

flynt-rs processes files in parallel (rayon; `RAYON_NUM_THREADS` to cap).
Output is byte-identical to the sequential mode: per-file stdout is buffered
and emitted in input order, and per-file counter states are merged, verified
against `RAYON_NUM_THREADS=1` and against Python flynt.

| Scenario | python flynt | flynt-rs | Speedup |
|---|---:|---:|---:|
| Django corpus, full conversion (2,400 files, 526 modified) | 4.678 s ± 0.155 | 0.213 s ± 0.003 | **21.9×** |
| Django corpus, no-op re-run (CI/linter scenario) | 3.628 s ± 0.011 | 0.163 s ± 0.004 | **22.2×** |
| Single large file (~4.4k lines) | 152.1 ms ± 4.3 | 14.2 ms ± 0.3 | **10.7×** |

Wall-clock includes interpreter/binary startup — that is the honest UX
comparison. Single-threaded (`RAYON_NUM_THREADS=1`), the corpus runs in
0.67 s / 0.46 s (6.9× / 8.3× vs Python) — parallelism contributes a further
~3× on this machine; single-file runs are unaffected (parallelism is
per-file).

## Divergences

Two entries, both documented in [DIVERGENCES.md](DIVERGENCES.md):
1. `escaped_newline.py` xfail mirrored (upstream bug #83, not replicated worse).
2. Redundant parens around generator expressions / unary `not` inside
   converted f-strings are omitted (cleaner, semantically identical output;
   CPython's `ast.unparse` emits them).

Also recorded there: `string_in_string.py` is *not* a divergence — flynt 1.0.6
on Python 3.13 reproduces the golden file exactly, so the original suite's
>=3.12 skip is moot here.

## How it was built

Orchestrated with parallel subagents on disjoint file ownership with pinned
interfaces: five Claude Opus 4.8 agents (core utils/unparser, percent
pipeline, .format pipeline, CodeEditor, CLI+api) and local codex gpt-5.6
(SPEC.md behavioral spec, string_concat + static_join). Byte-fidelity was
enforced by differential fixtures generated from Python flynt itself plus the
original golden files; the Django corpus differential caught the one real
unparser defect (f-string delimiter choice), fixed to match CPython's
`_str_literal_helper` algorithm.

Reproduce: `cargo test`; `cd harness && uv run --no-project --with pytest pytest`;
`bench/run_bench.sh`.
