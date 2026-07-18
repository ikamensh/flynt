#### v.2.0.0b1

* **flynt is now a native binary, rewritten in Rust.** `pip install flynt` ships
  a platform wheel containing the `flynt` executable — same CLI, same output,
  10–20× faster (files are processed in parallel; set `RAYON_NUM_THREADS=1` to
  disable). Verified against the full 1.x integration suite and byte-compared
  with 1.x over the Django 1.11 codebase (2400 files).
* **Breaking: the Python API (`import flynt`) is gone; 2.0 is CLI-only.** If you
  depend on `flynt.api` / `flynt.code_editor`, stay on `flynt<2`. All CLI
  flags are unchanged, and `python -m flynt` still works (the wheel ships a
  tiny shim that runs the binary). Accessing attributes of `import flynt`
  raises an error explaining the removal.
* **pre-commit:** keep `rev: '1.0.6'` during the beta — a 2.0 `rev` builds
  from source and needs a Rust toolchain. A wheel-backed hook comes with 2.0
  final.
* Behavior differences vs 1.x, both intentional (see DIVERGENCES.md):
  converted f-strings no longer contain redundant parentheses around generator
  expressions or unary `not`; everything else is byte-identical.
* Includes the `%c` conversion refusal fix (#254 / issue #253).

#### v.1.0.6

* minor efficiency improvement by removing some dead code

#### v.1.0.5

* added -nb / --notebook flag to convert .ipynb files. Note: the feature is not thoroughly tested yet, use with caution.

#### v.1.0.4
* Multiple bugfixes closing the issues accumulated over the years. Much of the credit goes to openai codex.
* Introduced -aa for double aggressive where we do dangerous changes like ignoring int conversion
in %d .
* better handling of escaped unicode characters, and multibyte unicode characters.

#### v.1.0.3

* Multiple bugfixes closing the issues accumulated over the years. Much of the credit goes to openai codex.


#### v.1.0.0

Drop support for python 3.7.

##### Moved % and .format expression identification to `ast` instead of legacy token state machine. 
This has led to small changes in formatting of output code, e.g. type of quotes in ambiguous cases 
might have changed. Example:
`'first part {}'"second part {}".format(one, two)` used to result in `"` quotes, 
and now results in `'`, as in `f'first part {one}second part {two}'`. I think it's a minor change
in the output. At the same time it's a huge simplification of the source code that should help 
maintain and develop this project in the future.

* Added `# flynt: skip` comment to ignore a line during conversion without using `# noqa`.


#### v.0.77

*[Contributed by Aarni Koskela]* `--transform-joins` (`-tj`) will transform string join operations on static operands
to an f-string.

*[Contributed by Aarni Koskela]* Fix handling of escaped unicode characters (#55 and #104).

*[Contributed by Aarni Koskela]* Add flags to disable percent statement / .format statement transformations: `--no-tp, --no-transform-percent` and 
`--no-tf, --no-transform-format`.

#### v.0.71

Added support to configuration via file.
For per-project configuration, use `pyproject.toml` file, [tool.flynt] section.
for global config, use `~/.config/flynt.toml` file.

#### v0.70

*[Contributed by Ryan Barrett]* Aggressive mode enables transforming expressions where same variable is used twice, 
e.g. `"""a = '%(?)s %(?)s' % {'?': var}"""` to `"""a = f'{var} {var}'"""` 

#### v.0.47

* added the changelog.
* added `-a / --aggressive` flag to enable risky 
(with behaviour potentially different from original) transformations. 
This currently includes "%5" % var -> f"{var:5}" transformation. 
Demo of unsafe behavior: 

```
print( "|%5s|%5d|%5d|" % ('111', 999_999, 77)  )
print( "|%5d|%5d|%5d|" % (111, 999_999, 77)  )

print( "|{:5s}|{:5}|{:5}|".format('111', 999_999, 77)  )
print( f"|{111:5}|{999_999:5}|{77:5}|" )

""" output:
|  111|999999|   77|
|  111|999999|   77|
|111  |999999|   77|  << behavior differs when printing a string
|  111|999999|   77|
"""
```

* %d format specifier is transformed only in `--aggressive` mode,
  resulting in `"%d" % var` -> `f"{int(var)}"`.
  Use `-aa` to omit the `int()` call.
  See https://github.com/ikamensh/flynt/issues/59.

* added short versions to other flags:
```
--line-length, -l
--transform-concats, -tc
--verbose, -v
--quiet, -q
--fail-on-change, -f
```

