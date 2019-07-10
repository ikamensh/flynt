# flynt - string formatting converter

**This is a beta release. Do NOT use on uncommitted code!**

`flynt` is a command line tool to automatically convert a project's Python code from old "%-formatted" and .format(...) strings into Python 3.6+'s "f-strings".

Read up on f-strings here: 
- https://realpython.com/python-f-strings/
- https://www.python.org/dev/peps/pep-0498/

### Installation

`flynt` can be installed by running `pip install flynt`.  It requires
Python 3.7+ to run and effectively turns the code it runs on into Python 3.6+,
since 3.6 is when "f-strings" were introduced.

### Usage

To run: `flynt {source_file_or_directory}`

* Given a single file, it will 'f-stringify' it: replace all applicable single line string formatting in this file (file will be modified).
* Given a folder, it will search the folder recursively and f-stringify all the .py files it finds. It skips some hard-coded folder names: `blacklist = {'.tox', 'venv', 'site-packages', '.eggs'}`.

### Command line options
```
usage: flynt [-h] [--verbose | --quiet] [--version] src

positional arguments:
  src         source file or directory

optional arguments:
  -h, --help  show this help message and exit
  --verbose   run with verbose output
  --quiet     run without output
  --version   show version and exit

```

### Sample output of a successful run:
```
38f9d3a65222:~ ikkamens$ git clone https://github.com/pallets/flask.git
Cloning into 'flask'...
remote: Enumerating objects: 17693, done.
remote: Total 17693 (delta 0), reused 0 (delta 0), pack-reused 17693
Receiving objects: 100% (17693/17693), 6.98 MiB | 6.96 MiB/s, done.
Resolving deltas: 100% (12203/12203), done.

38f9d3a65222:~ ikkamens$ flynt flask
fstringifying /Users/ikkamens/flask/setup.py...no
...
fstringifying /Users/ikkamens/flask/src/flask/json/tag.py...yes

Flynt run has finished. Stats:

Execution time: 0.818s
Files modified: 18
Expressions transformed: 43
Character count reduction: 241 (0.04%)

_-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_.

Please run your tests before commiting. Report bugs as github issues at: https://github.com/ikamensh/flynt
Thank you for using flynt! Fstringify more projects and recommend it to your colleagues!

_-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_.
38f9d3a65222:~ ikkamens$
```

### About

F-Strings:

> Not only are they more readable, more concise, and less prone to error than other ways of formatting, but they are also faster!

After obsessively refactoring a project at work, and not even covering 50% of f-string candidates, I realized there was some place for automation. Also it was very interesting to work with ast module. 

### Other Credits / Dependencies / Links

- [fstringify](https://github.com/jacktasia/fstringify) - this project was forked from fstringify, but undergone some heavy refactoring.
- [astor](https://github.com/berkerpeksag/astor) is used to turn the transformed AST back into code.
- Thanks to folks from [pyddf](https://www.pyddf.de/) for their support, advice and participation during spring hackathon 2019, in particular Holger Hass, Farid Muradov, Charlie Clark.
