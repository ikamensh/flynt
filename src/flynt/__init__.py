"""`flynt` is a command line tool to automatically convert a project's Python code
from old "%-formatted" and .format(...) strings into Python 3.6+'s f-strings.
Learn more about f-strings at https://www.python.org/dev/peps/pep-0498/"""

__version__ = "1.0.5"

try:
    from ._git_version import version as __version__  # type: ignore
except Exception:  # noqa: S110 - silence "try-except-pass" lint when file is absent
    # _git_version.py is only generated during a build; fall back to the
    # static version defined above when running from a source checkout.
    pass

from flynt.cli import main

__all__ = ["main", "__version__"]
