# flynt - string formatting converter

<p align="center">
<a href="https://github.com/ikamensh/flynt/actions"><img alt="Actions Status" src="https://github.com/ikamensh/flynt/workflows/Test/badge.svg"></a>
<a href="https://github.com/ikamensh/flynt/blob/main/LICENSE"><img alt="License: MIT" src="https://black.readthedocs.io/en/stable/_static/license.svg"></a>
<a href="https://pypi.org/project/flynt/"><img alt="PyPI" src="https://img.shields.io/pypi/v/flynt"></a>
<a href="https://pepy.tech/project/flynt"><img alt="Downloads" src="https://pepy.tech/badge/flynt"></a>
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

`flynt` is a command line tool to automatically convert a project's Python code from old "%-formatted" and .format(...) strings into Python 3.6+'s "f-strings".

F-Strings:

> Not only are they more readable, more concise, and less prone to error than other ways of formatting, but they are also faster!

### Installation

`pip install flynt`. It requires Python version 3.9+.

### Usage

*Flynt will modify the files it runs on. Add your project to version control system before using flynt.*

To run: `flynt {source_file_or_directory}`

* Given a single file, it will 'f-stringify' it: replace all applicable string formatting in this file (file will be modified).
* Given a folder, it will search the folder recursively and f-stringify all the .py files it finds. It skips some hard-coded folder names: `blacklist = {'.tox', 'venv', 'site-packages', '.eggs'}`.

It turns the code it runs on into Python 3.6+, since 3.6 is when "f-strings" were introduced.

### Command line options

From the output of `flynt -h`:

<!-- begin-options -->
```
usage: flynt [-h] [-v | -q] [--no-multiline | -ll LINE_LENGTH]
             [-d | --stdout] [-s] [--no-tp] [--no-tf] [-tc] [-tj]
             [-f] [-a] [-e EXCLUDE [EXCLUDE ...]] [--version]
             [--report]
             [src ...]

flynt v.1.0.3

positional arguments:
  src                   source file(s) or directory (or a single `-`
                        to read stdin and output to stdout)

options:
  -h, --help            show this help message and exit
  -v, --verbose         run with verbose output
  -q, --quiet           run without outputting statistics to stdout
  --no-multiline        convert only single line expressions
  -ll, --line-length LINE_LENGTH
                        for expressions spanning multiple lines,
                        convert only if the resulting single line
                        will fit into the line length limit. Default
                        value is 88 characters.
  -d, --dry-run         Do not change the files in-place and print
                        the diff instead. Note that this must be
                        used in conjunction with '--fail-on-change'
                        when used for linting purposes.
  --stdout              Do not change the files in-place and print
                        the result instead. This argument implies
                        --quiet, i.e. no statistics are printed to
                        stdout, only the resulting code. It is
                        incompatible with --dry-run and --verbose.
  -s, --string          Interpret the input as a Python code snippet
                        and print the converted version. The snippet
                        must use single quotes or escaped double
                        quotes.
  --no-tp, --no-transform-percent
                        Don't transform % formatting to f-strings
                        (default: do so)
  --no-tf, --no-transform-format
                        Don't transform .format formatting to
                        f-strings (default: do so)
  -tc, --transform-concats
                        Replace string concatenations (defined as +
                        operations involving string literals) with
                        f-strings. Available only if flynt is
                        installed with a 3.9+ interpreter.
  -tj, --transform-joins
                        Replace static joins (where the joiner is a
                        string literal and the joinee is a static-
                        length list) with f-strings. Available only
                        if flynt is installed with a 3.9+
                        interpreter.
  -f, --fail-on-change  Fail when changing files (for linting
                        purposes)
  -a, --aggressive      Include conversions with potentially changed
                        behavior.
  -e, --exclude EXCLUDE [EXCLUDE ...]
                        ignore files with given strings in it's
                        absolute path.
  --version             Print the current version number and exit.
  --report              Show detailed conversion report

```

### Sample output of a successful run:
```
$ git clone https://github.com/pallets/flask.git
Cloning into 'flask'...
...
Resolving deltas: 100% (12203/12203), done.

$ flynt flask
Running flynt v.1.0.3
Modified 21 of 70 files in 0.79s
$
```

### Pre-commit hook

To make sure all formatted strings are always converted to f-strings, you can
add flynt to your [pre-commit](https://www.pre-commit.com) hooks.

Add a new section to `.pre-commit-config.yaml`:
```
-   repo: https://github.com/ikamensh/flynt/
    rev: ''
    hooks:
    -   id: flynt
```

This will run flynt on all modified files before committing.

You can skip conversion of certain lines by adding `# noqa [: anything else] flynt [anything else]` or `# flynt: skip`


### Configuration files

Since v0.71 flynt can be configured using `pyproject.toml` file on a per-project basis. 
Use same arguments as in CLI, and add them to `[tool.flynt]` section. CLI arguments takes precedence over the config file.
It can also be configured globally with a toml file located in `~/.config/flynt.toml` on Unix / `~/.flynt.toml` on Windows.

### About

Read up on f-strings here:
- https://realpython.com/python-f-strings/
- https://www.python.org/dev/peps/pep-0498/

After obsessively refactoring a project at work, and not even covering 50% of f-string candidates, I realized there was some place for automation. Also it was very interesting to work with ast module.

### Dangers of conversion
It is not guaranteed that formatted strings will be exactly the same as before conversion.

`'%s' % var` is converted to `f'{var}'`. There is a case when this will behave different from the original -  if var is a tuple of one element. In this case, %s displays the element, and f-string displays the tuple. Example:

```
foo = (1,)
print('%s' % foo) # prints '1'
print(f'{foo}')   # prints '(1,)'
```

Furthermore, some arguments cause formatting of strings to throw exceptions. One example where f-strings are inconsistent with previous formatting is %d vs {:d} - new format no longer accepts floats. While most cases are covered by taking the formatting specifiers to the f-strings format, the precise exception behaviour might differ as well. Make sure you have sufficient test coverage.

### Other Credits / Dependencies / Links

- Python's built-in `ast.unparse` is used to turn the transformed AST back into code.
- Thanks to folks from [pyddf](https://www.pyddf.de/) for their support, advice and participation during spring hackathon 2019, in particular Holger Hass, Farid Muradov, Charlie Clark.
- Logic finding the pyproject.toml and parsing it was partially copied from [black](https://github.com/psf/black) 
