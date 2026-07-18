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

## 2. Redundant parentheses inside converted f-strings omitted

- **Python flynt**: CPython's `ast.unparse` always parenthesizes generator
  expressions, so a converted `"...".format(", ".join(x for y in z))` style
  chunk renders as `{', '.join((q.name for q in self.qualifications.all()))}`.
- **flynt-rs**: emits the cleaner, equally valid
  `{', '.join(q.name for q in self.qualifications.all())}` (no redundant
  parens around a sole-argument genexp).
- **Same family**: CPython also parenthesizes a unary `not` used as a BoolOp
  operand (`a and (not b)`); flynt-rs emits `a and not b`. One occurrence in
  the Django corpus (`django/http/request.py`). Also tuple displays before a
  conversion: `"_Feature" + repr((a, b, c))` renders as `f"_Feature{a, b, c!r}"`
  (cpython `Lib/__future__.py`); `!r` binds to the whole expression, so the
  value is identical to the parenthesized form.
- **Why better**: output is what a human would write; semantics identical.
  Not pinned by any original golden file (verified: full original integration
  suite passes). 16 of 2400 files on a Django 1.11 differential run differ,
  all in this class; everything else is byte-identical to Python flynt.
- **Knock-on effect** (1 file in 2400): because the paren-free rendering is
  2 chars shorter, a multiline chunk can fit the default 88-char limit and be
  converted where Python flynt skips it (`tests/fixtures/models.py` in Django
  1.11). Consistent with flynt's own rule: the limit applies to the actually
  emitted text.

## 3. stdin (`flynt -`) trailing-character handling fixed

- **Python flynt**: `sys.stdin.read()[:-len(os.linesep)]` chops characters
  unconditionally — on Windows it eats the last real character (text-mode
  stdin already collapsed `\r\n` to `\n` but `len(os.linesep)` is 2), and on
  any platform it corrupts input that lacks a trailing newline.
- **flynt 2.0**: strips at most one trailing newline (`\n` or `\r\n`).
  Identical behavior for the normal Unix pipe case; correct on Windows and
  for unterminated input.
- **Why better**: the 1.x behavior is a plain bug; caught by Windows CI.

## 4. Help/usage text line-wrapping (cosmetic)

- **Python flynt**: argparse wraps `--help` and usage-on-error output to the
  terminal width (80 columns when piped).
- **flynt 2.0**: `--help` is a fixed 70-column snapshot (the README
  embedding); usage-on-error is emitted on a single line.
- Same words, different line breaks; exit codes and error text identical
  (verified by a 24-case CLI parity matrix against 1.0.6).

## 5. Nested format-spec placeholders in `.format()` are converted

- **Python flynt**: refuses `"{:.{p}f}".format(v, p=prec)` (keyword used only
  inside a nested format spec); worse, for the duplicate-use case
  `"{x:{x}}".format(x=a)` it emits `f'{a:{{x}}}'`, which raises at runtime
  (the spec becomes the literal text `{x}`).
- **flynt 2.0**: converts the safe cases (`f"{v:.{prec}f}"` — found on
  `rich/filesize.py`) and refuses the duplicate-use case like every other
  duplicate, so no broken output.
- **Why better**: more conversions, all semantics-preserving; the one case
  1.x "converted" was a bug.

## 6. No whole-file bail-outs on transformer errors

- **Python flynt**: an internal exception in one pipeline (e.g. its static-join
  transformer crashing on cpython's `Lib/smtplib.py` under `-tc -tj`) is caught
  per *file*, so the file is silently left with **zero** conversions — including
  the safe `%`-format ones other pipelines had already produced.
- **flynt 2.0**: pipelines refuse per candidate; a refused candidate never
  discards the rest of the file's conversions.

(Entries below added during integration burn-down.)
