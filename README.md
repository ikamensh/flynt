# flynt - string formatting converter
[![Build Status](https://dev.azure.com/ikamenshchikov/flynt/_apis/build/status/ikamensh.flynt?branchName=master)](https://dev.azure.com/ikamenshchikov/flynt/_build/latest?definitionId=1&branchName=master)  [![PyPI version](https://badge.fury.io/py/flynt.svg)](https://badge.fury.io/py/flynt)  [![Downloads](https://pepy.tech/badge/flynt)](https://pepy.tech/project/flynt)

**This is a beta release. Do NOT use on uncommitted code!**

`flynt` is a command line tool to automatically convert a project's Python code from old "%-formatted" and .format(...) strings into Python 3.6+'s "f-strings".

F-Strings:

> Not only are they more readable, more concise, and less prone to error than other ways of formatting, but they are also faster!

### Installation

`pip install flynt`. It requires Python version 3.6+.  
 
### Usage

To run: `flynt {source_file_or_directory}`

* Given a single file, it will 'f-stringify' it: replace all applicable string formatting in this file (file will be modified).
* Given a folder, it will search the folder recursively and f-stringify all the .py files it finds. It skips some hard-coded folder names: `blacklist = {'.tox', 'venv', 'site-packages', '.eggs'}`.

It turns the code it runs on into Python 3.6+, since 3.6 is when "f-strings" were introduced.

### Command line options
```
usage: flynt [-h] [--verbose | --quiet]
             [--no_multiline | --line_length LINE_LENGTH]
             src

positional arguments:
  src                   source file or directory

optional arguments:
  -h, --help            show this help message and exit
  --verbose             run with verbose output
  --quiet               run without output
  --no_multiline        convert only single line expressions
  --line_length LINE_LENGTH
                        for expressions spanning multiple lines, convert only
                        if the resulting single line will fit into the line
                        length limit. Default value is 79 characters.
  --upgrade             run pyupgrade on .py files

```

### Sample output of a successful run:
```
38f9d3a65222:~ ikkamens$ git clone https://github.com/pallets/flask.git
Cloning into 'flask'...
...
Resolving deltas: 100% (12203/12203), done.

38f9d3a65222:~ ikkamens$ flynt flask

Flynt run has finished. Stats:

Execution time: 0.623s
Files modified: 18
Expressions transformed: 43
Character count reduction: 241 (0.04%)

_-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_.

Please run your tests before commiting. Report bugs as github issues at: https://github.com/ikamensh/flynt
Thank you for using flynt! Fstringify more projects and recommend it to your colleagues!

_-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_.
38f9d3a65222:~ ikkamens$
```

### Pre-commit hook

To make sure all formatted strings are always converted to f-strings, you can
add flynt to your [pre-commit](https://www.pre-commit.com) hooks.

Add a new section to `.pre-commit-config.yaml`:
```
   - repo: local
     hooks:
         - id: flynt
           name: flynt
           entry: flynt
           args: [--fail-on-change]
           types: [python]
           language: python
           additional_dependencies:
               - flynt
```

This will run flynt on all modified files before commiting.


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

Furthermore, some arguments cause formatting of strings to throw exceptions, e.g. print('%d' % 'bla'). While most cases are covered by taking the formatting specifiers to the f-strings format, the precise exception behaviour might differ as well.

### Other Credits / Dependencies / Links

- [astor](https://github.com/berkerpeksag/astor) is used to turn the transformed AST back into code.
- Thanks to folks from [pyddf](https://www.pyddf.de/) for their support, advice and participation during spring hackathon 2019, in particular Holger Hass, Farid Muradov, Charlie Clark.
