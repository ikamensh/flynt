import pathlib
from typing import Callable, Tuple

int_test_path = pathlib.Path(__file__).parent

EXCLUDED = {
    "bom.py",
    "class.py",
    "escaped_newline.py",  # not supported yet, #83 on github
    "multiline_limit.py",
}
samples = {p.name for p in (int_test_path / "samples_in").glob("*.py")} - EXCLUDED
# samples = {"multiline_1.py"}
concat_samples = {p.name for p in (int_test_path / "samples_in_concat").glob("*.py")}


def try_on_file(
    filename: str,
    func: Callable[[str], Tuple[str, int]],
    suffix: str = "",
    out_suffix: str = "",
) -> Tuple[str, str]:
    """Try `flynt`ifying a file.

    Given a file name (something.py),
    * find it in test/integration/samples_in[suffix],
    * run the given function (expected to return (out, edits)) on it,
    * write the result to test/integration/actual_out[suffix]/something.py,
    * and compare the result with test/integration/expected_out[suffix]/something.py"""
    if not out_suffix:
        out_suffix = suffix

    txt_in = (int_test_path / f"samples_in{suffix}" / filename).read_text()
    ex_path = int_test_path / f"expected_out{out_suffix}" / filename
    if not ex_path.exists() and out_suffix:
        ex_path = int_test_path / "expected_out" / filename
    ex = ex_path.read_text()
    out, edits = func(txt_in)
    out_path = int_test_path / f"actual_out{out_suffix}" / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out)
    return out, ex
