"""Demonstrations for issue #106 about conversion field equivalence.

The f-string conversion specifiers ``!s``, ``!r`` and ``!a`` internally call
``str()``, ``repr()`` and ``ascii()`` respectively.  This script shows:

* objects with and without ``__format__`` behave identically when using ``!s``,
  ``!r`` and ``!a`` compared with explicit function calls;
* overriding the built-in names ``str``/``repr``/``ascii`` breaks this
  equivalence.

Python's bytecode for ``f"{x!s}"`` uses the ``FORMAT_VALUE`` opcode with a
conversion flag. This always resolves to the real built-in functions even if the
names ``str`` or ``repr`` are shadowed in the local scope. Therefore, barring
such shadowing, ``f"{x!s}"`` is equivalent to ``f"{str(x)}"`` for all objects.

Run this file directly to print the examples.
"""


class Custom:
    """Defines ``__format__`` in addition to ``__str__`` and ``__repr__``."""

    def __format__(self, spec: str) -> str:
        return f"formatted({spec})"

    def __str__(self) -> str:
        return "string"

    def __repr__(self) -> str:
        return "repr"


class WithoutFormat:
    """Lacks a ``__format__`` implementation."""

    def __str__(self) -> str:
        return "plain-str"

    def __repr__(self) -> str:
        return "plain-repr"


def demonstrate(obj) -> None:
    print("object:", obj)
    print("default f-string:", f"{obj}")
    print("f'{obj!s}':", f"{obj!s}")
    print("f'{str(obj)}':", f"{str(obj)}")
    print("f'{obj!r}':", f"{obj!r}")
    print("f'{repr(obj)}':", f"{repr(obj)}")
    print("f'{obj!a}':", f"{obj!a}")
    print("f'{ascii(obj)}':", f"{ascii(obj)}")
    print()


def shadowed_demo() -> None:
    print("Shadowing built-ins breaks equivalence:")

    def str(x):  # noqa: A001
        return "shadowed-str"

    def repr(x):  # noqa: A001
        return "shadowed-repr"

    def ascii(x):  # noqa: A001
        return "shadowed-ascii"

    obj = Custom()
    print("f'{obj!s}':", f"{obj!s}")
    print("f'{str(obj)}':", f"{str(obj)}")
    print("f'{obj!r}':", f"{obj!r}")
    print("f'{repr(obj)}':", f"{repr(obj)}")
    print("f'{obj!a}':", f"{obj!a}")
    print("f'{ascii(obj)}':", f"{ascii(obj)}")
    print()


def main() -> None:
    values = [123, 45.6, "text", Custom(), WithoutFormat()]
    for value in values:
        demonstrate(value)
    shadowed_demo()


if __name__ == "__main__":
    main()
