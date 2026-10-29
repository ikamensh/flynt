"""Integer precision has no equivalent general f-string format specifier."""

import pytest

from conftest import run_pipeline


@pytest.mark.parametrize("aggressive", [0, 1, 2])
@pytest.mark.parametrize("operand", ["value", "(value,)", "{'value': value}"])
@pytest.mark.parametrize(
    "specifier",
    [".4d", "8.4i", "+8.4u", "-8.4o", "#8.4x", "4.4X", "08.4x", ".0x", ".x"],
)
def test_integer_precision_is_left_unchanged(aggressive, operand, specifier):
    key = "(value)" if operand.startswith("{") else ""
    source = f'result = "%{key}{specifier}" % {operand}\n'
    output, count = run_pipeline(source, aggressive=aggressive)
    assert output == source
    assert count == 0
    for value in [-255, -1, 0, 1, 255]:
        original = {"value": value}
        converted = {"value": value}
        exec(source, original)
        exec(output, converted)
        assert converted["result"] == original["result"]


@pytest.mark.parametrize(
    "expression",
    [
        '"%08x" % value',
        '"%8X" % (value,)',
        '"%8o" % value',
        '"%+8d" % int(value)',
        '"%8i" % int(value)',
        '"%8u" % int(value)',
        '"%8.4f" % value',
        '"%+.2e" % value',
        '"progress=%.2f%%" % value',
    ],
)
def test_precision_refusal_preserves_other_numeric_conversions(expression):
    source = f"result = {expression}\n"
    output, count = run_pipeline(source)
    assert count == 1
    for value in [-255, -1, 0, 1, 255]:
        original = {"value": value}
        converted = {"value": value}
        exec(source, original)
        exec(output, converted)
        assert converted["result"] == original["result"]
