# Documented divergences from Python flynt 1.0.6

Each entry: sample / behavior, what Python flynt does, what flynt-rs does, why.

## 1. `string_in_string.py` — nested quotes in f-strings

- **Python flynt**: output depends on interpreter version; the original test
  suite *skips this sample on Python >= 3.12* with the comment "3.12 behavior
  is preferable". `expected_out/string_in_string.py` pins the pre-3.12
  behavior.
- **flynt-rs**: implements the 3.12+ (preferable) behavior; pinned in
  `harness/expected_out_rust/string_in_string.py`.
- **Why**: the original authors call this behavior preferable; replicating the
  pre-3.12 quirk would mean reproducing a workaround for old interpreters.

## 2. `escaped_newline.py` — escaped newlines lost (flynt issue #83)

- **Python flynt**: known bug, marked `xfail` in the original suite.
- **flynt-rs**: mirrors the xfail (not converted / same limitation) unless the
  port turns out to handle it correctly, in which case the test flips to pass
  and this entry documents the improvement.

(Entries below added during integration burn-down.)
