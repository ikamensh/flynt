"""Golden-file tests: byte-identical port of the original flynt integration
suite (test_files.py, test_concat.py, test_files_len_limit.py, test_issue83.py)
driving the Rust binary instead of the Python API.

Skips/xfails mirror the original suite exactly:
- EXCLUDED set from test/integration/utils.py
- escaped_newline.py xfail (flynt issue #83)
- string_in_string.py: original skips on Python >= 3.12 ("3.12 behavior is
  preferable"); we pin the improved behavior in expected_out_rust/ instead.
  See DIVERGENCES.md.
"""

import pytest

from conftest import INT_DIR, HARNESS_DIR, golden, run_pipeline

EXCLUDED = {
    "bom.py",
    "class.py",
    "escaped_newline.py",  # not supported yet, #83 on github
    "multiline_limit.py",
}
SKIP_PY312 = {"string_in_string.py"}

samples = sorted(
    {p.name for p in (INT_DIR / "samples_in").glob("*.py")} - EXCLUDED - SKIP_PY312
)
concat_samples = sorted(p.name for p in (INT_DIR / "samples_in_concat").glob("*.py"))


@pytest.mark.parametrize("filename", samples)
def test_fstringify(filename):
    txt_in, expected = golden(filename)
    out, _count = run_pipeline(txt_in)
    assert out == expected


@pytest.mark.parametrize("filename", samples)
def test_fstringify_single_line(filename):
    txt_in, expected = golden(filename, out_suffix="_single_line")
    out, _count = run_pipeline(txt_in, multiline=False)
    assert out == expected


@pytest.mark.parametrize("enable", ["percent_only", "format_only"])
def test_fstringify_enables(enable):
    txt_in, expected = golden(
        "sample.py", suffix="_enable", out_suffix=f"_enable_{enable}"
    )
    out, _count = run_pipeline(
        txt_in,
        multiline=False,
        len_limit=None,
        transform_percent=(enable == "percent_only"),
        transform_format=(enable == "format_only"),
    )
    assert out == expected


@pytest.mark.parametrize("filename", concat_samples)
def test_fstringify_concat(filename):
    txt_in, expected = golden(filename, suffix="_concat")
    out1, _ = run_pipeline(txt_in)
    out2, _ = run_pipeline(out1, pipeline="concat")
    assert out2 == expected


def test_multiline_limit_concats():
    txt_in, expected = golden("multiline_limit.py")
    out, _count = run_pipeline(txt_in, pipeline="concat")
    assert out == expected


@pytest.mark.xfail(reason="newline escapes lost, issue #83 (matches original xfail)")
def test_escaped_newline():
    txt_in, expected = golden("escaped_newline.py")
    out, _count = run_pipeline(txt_in)
    assert out == expected


def test_string_in_string_py312_behavior():
    """Original suite skips this sample on >=3.12 because behavior improved.
    We implement the improved (3.12+) behavior; pinned expected output lives
    in harness/expected_out_rust/. Generated from python3.13 + original flynt."""
    pin = HARNESS_DIR / "expected_out_rust" / "string_in_string.py"
    if not pin.exists():
        pytest.skip("pin file not yet generated (see task #10)")
    txt_in, _ = golden("string_in_string.py")
    out, _count = run_pipeline(txt_in)
    assert out == pin.read_text()
