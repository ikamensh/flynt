"""Pytest harness driving the flynt binary with the flynt 1.x golden
integration fixtures (../test/integration).

The binary exposes a machine mode `--harness-json` mirroring the Python 1.x
functions the original tests called directly:
    fstringify_code_by_line / fstringify_concats / fstringify_static_joins
"""

import json
import pathlib
import subprocess
import sys

import pytest

HARNESS_DIR = pathlib.Path(__file__).parent
REPO_DIR = HARNESS_DIR.parent
INT_DIR = REPO_DIR / "test" / "integration"
BINARY = REPO_DIR / "target" / "debug" / ("flynt.exe" if sys.platform == "win32" else "flynt")


@pytest.fixture(scope="session", autouse=True)
def build_binary():
    subprocess.run(["cargo", "build"], cwd=REPO_DIR, check=True)


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
