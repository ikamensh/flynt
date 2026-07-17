"""Pytest harness driving the flynt-rs binary with the ORIGINAL flynt
integration fixtures (../../flynt/test/integration).

The binary exposes a machine mode `--harness-json` mirroring the Python
functions the original tests call directly:
    fstringify_code_by_line / fstringify_concats / fstringify_static_joins
"""

import json
import pathlib
import subprocess

import pytest

HARNESS_DIR = pathlib.Path(__file__).parent
RUST_DIR = HARNESS_DIR.parent
FLYNT_REPO = RUST_DIR.parent / "flynt"
INT_DIR = FLYNT_REPO / "test" / "integration"
BINARY = RUST_DIR / "target" / "debug" / "flynt-rs"


@pytest.fixture(scope="session", autouse=True)
def build_binary():
    subprocess.run(["cargo", "build"], cwd=RUST_DIR, check=True)


def run_pipeline(code: str, pipeline: str = "fstring", **state):
    """Run one pipeline of the Rust binary; mirrors calling e.g.
    fstringify_code_by_line(code, state=State(**state))."""
    req = {"code": code, "pipeline": pipeline, "state": state}
    proc = subprocess.run(
        [str(BINARY), "--harness-json"],
        input=json.dumps(req),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"binary failed: {proc.stderr}"
    resp = json.loads(proc.stdout)
    return resp["out"], resp["count"]


def golden(filename: str, suffix: str = "", out_suffix: str = ""):
    """Port of test/integration/utils.py::try_on_file's file resolution:
    returns (input_text, expected_text)."""
    if not out_suffix:
        out_suffix = suffix
    txt_in = (INT_DIR / f"samples_in{suffix}" / filename).read_text()
    ex_path = INT_DIR / f"expected_out{out_suffix}" / filename
    if not ex_path.exists() and out_suffix:
        ex_path = INT_DIR / "expected_out" / filename
    return txt_in, ex_path.read_text()
