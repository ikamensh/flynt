"""flynt 2.0 is a native command-line tool; the Python import API is gone.

Run it as ``flynt`` or ``python -m flynt``. If you need the 1.x API
(``flynt.api``, ``flynt.code_editor``, ...), pin ``flynt<2``.
"""

__version__ = "2.0.0b2"


def __getattr__(name):
    raise AttributeError(
        f"module 'flynt' has no attribute {name!r}: flynt 2.0 is a native "
        "binary with no Python API. Pin flynt<2 if you need the 1.x API. "
        "See https://github.com/ikamensh/flynt/blob/master/CHANGELOG.md"
    )
