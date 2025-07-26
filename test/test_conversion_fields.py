import pytest


class FormatVsStr:
    def __format__(self, spec: str) -> str:
        return f"FMT<{spec}>"

    def __str__(self) -> str:
        return "STR"

    def __repr__(self) -> str:
        return "REPR"


@pytest.mark.parametrize("obj", [1, 1.5, "text", FormatVsStr()])
def test_str_equivalence(obj):
    assert f"{obj!s}" == f"{str(obj)}"


@pytest.mark.parametrize("obj", [1, 1.5, "text", FormatVsStr()])
def test_repr_equivalence(obj):
    assert f"{obj!r}" == f"{repr(obj)}"


@pytest.mark.parametrize("obj", ["\u00e9", FormatVsStr()])
def test_ascii_equivalence(obj):
    assert f"{obj!a}" == f"{ascii(obj)}"


def test_format_diff():
    obj = FormatVsStr()
    assert f"{obj}" != f"{obj!s}"
    assert f"{obj!s}" == str(obj)


class WithoutFormat:
    def __str__(self) -> str:
        return "W_STR"

    def __repr__(self) -> str:
        return "W_REPR"


@pytest.mark.parametrize("obj", [WithoutFormat()])
def test_without_format(obj):
    # object lacking __format__ uses str for default f-string
    assert f"{obj}" == str(obj)
    assert f"{obj!s}" == f"{str(obj)}"
    assert f"{obj!r}" == f"{repr(obj)}"
    assert f"{obj!a}" == f"{ascii(obj)}"


def test_shadowing_breaks_equivalence():
    def str(x):  # noqa: A001
        return "shadow"

    def repr(x):  # noqa: A001
        return "shadow"

    def ascii(x):  # noqa: A001
        return "shadow"

    obj = WithoutFormat()
    assert f"{obj!s}" != f"{str(obj)}"
    assert f"{obj!r}" != f"{repr(obj)}"
    assert f"{obj!a}" != f"{ascii(obj)}"
