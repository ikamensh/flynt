"""`flynt` is a command line tool to automatically convert a project's Python code
from old "%-formatted" and .format(...) strings into Python 3.6+'s f-strings.
Learn more about f-strings at https://www.python.org/dev/peps/pep-0498/"""

__version__ = "1.0.4"

from flynt.cli import main

__all__ = ["main", "__version__"]
