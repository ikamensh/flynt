# Documented divergences from Python flynt 1.0.6

Each entry: sample / behavior, what Python flynt does, what flynt-rs does, why.

## Non-divergence: `string_in_string.py`

The original suite skips this sample on Python >= 3.12, suggesting behavior
differs. Verified 2026-07-16: flynt 1.0.6 on python 3.13 reproduces
`expected_out/string_in_string.py` exactly (both multiline and single-line
states), so flynt-rs treats it as a regular golden sample. No divergence.

## 1. `escaped_newline.py` — escaped newlines lost (flynt issue #83)

- **Python flynt**: known bug, marked `xfail` in the original suite.
- **flynt-rs**: mirrors the xfail (not converted / same limitation) unless the
  port turns out to handle it correctly, in which case the test flips to pass
  and this entry documents the improvement.

(Entries below added during integration burn-down.)
