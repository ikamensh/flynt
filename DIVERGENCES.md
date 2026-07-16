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

## 2. Generator expressions inside converted f-strings: no redundant parens

- **Python flynt**: CPython's `ast.unparse` always parenthesizes generator
  expressions, so a converted `"...".format(", ".join(x for y in z))` style
  chunk renders as `{', '.join((q.name for q in self.qualifications.all()))}`.
- **flynt-rs**: emits the cleaner, equally valid
  `{', '.join(q.name for q in self.qualifications.all())}` (no redundant
  parens around a sole-argument genexp).
- **Why better**: output is what a human would write; semantics identical.
  Not pinned by any original golden file (verified: full original integration
  suite passes). Found in 6 of 2400 files on a Django 1.11 differential run.
- **Knock-on effect** (1 file in 2400): because the paren-free rendering is
  2 chars shorter, a multiline chunk can fit the default 88-char limit and be
  converted where Python flynt skips it (`tests/fixtures/models.py` in Django
  1.11). Consistent with flynt's own rule: the limit applies to the actually
  emitted text.

(Entries below added during integration burn-down.)
