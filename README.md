# flynt - string formatting converter
[![Build Status](https://dev.azure.com/ikamenshchikov/flynt/_apis/build/status/ikamensh.flynt?branchName=master)](https://dev.azure.com/ikamenshchikov/flynt/_build/latest?definitionId=1&branchName=master) ![Coverage](https://img.shields.io/azure-devops/coverage/ikamenshchikov/flynt/1) [![PyPI version](https://badge.fury.io/py/flynt.svg)](https://badge.fury.io/py/flynt)  [![Downloads](https://pepy.tech/badge/flynt)](https://pepy.tech/project/flynt)  [![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)


`flynt` is a command line tool to automatically convert a project's Python code from old "%-formatted" and .format(...) strings into Python 3.6+'s "f-strings".

F-Strings:

> Not only are they more readable, more concise, and less prone to error than other ways of formatting, but they are also faster!

### Installation

`pip install flynt`. It requires Python version 3.6+.  
 
### Usage

*Flynt will modify the files it runs on. Add your project to version control system before using flynt.*

To run: `flynt {source_file_or_directory}`

* Given a single file, it will 'f-stringify' it: replace all applicable string formatting in this file (file will be modified).
* Given a folder, it will search the folder recursively and f-stringify all the .py files it finds. It skips some hard-coded folder names: `blacklist = {'.tox', 'venv', 'site-packages', '.eggs'}`.

It turns the code it runs on into Python 3.6+, since 3.6 is when "f-strings" were introduced.

### Command line options
```
flynt v.0.48

usage:  flynt [-h] [-v | -q] 
        [--no-multiline | -ll LINE_LENGTH] 
        [-tc] [-f] [-a] [-e EXCLUDE [EXCLUDE ...]] 
        src [src ...]

positional arguments:
  src                   source file(s) or directory

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         run with verbose output
  -q, --quiet           run without output
  --no-multiline        convert only single line expressions
  -ll LINE_LENGTH, --line-length LINE_LENGTH
                        for expressions spanning multiple lines, convert only if the resulting single line will fit into the line length limit. Default value is 88 characters.
  -d, --dry-run         Do not change the files in-place and print the diff
                        instead. 
  -tc, --transform-concats
                        Replace string concatenations (defined as + operations involving string literals) with f-strings. Available only if flynt is installed with 3.8+
                        interpreter.
  -f, --fail-on-change  Fail when changing files (for linting purposes)
  -a, --aggressive      Include conversions with potentially changed behavior.
  -e EXCLUDE [EXCLUDE ...], --exclude EXCLUDE [EXCLUDE ...]
                        ignore files with given strings in it's absolute path.
  --version             Print the current version number and exit.
```

### Sample output of a successful run:
```
38f9d3a65222:~ ikkamens$ git clone https://github.com/pallets/flask.git
Cloning into 'flask'...
...
Resolving deltas: 100% (12203/12203), done.

38f9d3a65222:open_source ikkamens$ flynt flask
Running flynt v.0.40

Flynt run has finished. Stats:

Execution time:                            0.789s
Files modified:                            21
Character count reduction:                 299 (0.06%)

Per expression type:
Old style (`%`) expressions attempted:     40/42 (95.2%)
`.format(...)` calls attempted:            26/33 (78.8%)
F-string expressions created:              48
Out of all attempted transforms, 7 resulted in errors.
To find out specific error messages, use --verbose flag.

_-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_.
Please run your tests before commiting. Did flynt get a perfect conversion? give it a star at:
~ https://github.com/ikamensh/flynt ~
Thank you for using flynt. Upgrade more projects and recommend it to your colleagues!

38f9d3a65222:~ ikkamens$
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

This will run flynt on all modified files before commiting.

You can skip conversion of certain lines by adding `# noqa [: anything else] flynt [anything else]`


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

- [astor](https://github.com/berkerpeksag/astor) is used to turn the transformed AST back into code.
- Thanks to folks from [pyddf](https://www.pyddf.de/) for their support, advice and participation during spring hackathon 2019, in particular Holger Hass, Farid Muradov, Charlie Clark.
