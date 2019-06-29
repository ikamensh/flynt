# flynt - string formatting converter

**This is a beta release. Do NOT use on uncommitted code!**

`flynt` is a command line tool to automatically convert a project's Python code from old "%-formatted" and .format(...) strings into Python 3.6+'s "f-strings".

Read up on f-strings here: 
- https://realpython.com/python-f-strings/
- https://www.python.org/dev/peps/pep-0498/

### About

F-Strings:

> Not only are they more readable, more concise, and less prone to error than other ways of formatting, but they are also faster!

After obsessively refactoring a project at work, and not even covering 50% of f-string candidates, I realized there was some place for automation. Also it was very interesting to work with ast module. 

### Installation

`flynt` can be installed by running `pip install flynt`.  It requires
Python 3.7+ to run and effectively turns the code it runs on into Python 3.6+,
since 3.6 is when "f-strings" were introduced.


### Usage

To run: `flynt {source_file_or_directory}`


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

### Other Credits / Dependencies / Links

- [fstringify](https://github.com/jacktasia/fstringify) - this project was forked from fstringify, but undergone some heavy refactoring.
- [astor](https://github.com/berkerpeksag/astor) is used to turn the transformed AST back into code.
- Thanks to folks from [pyddf](https://www.pyddf.de/) for their support, advice and participation during spring hackathon 2019, in particular Holger Hass, Farid Muradov, Charlie Clark.
