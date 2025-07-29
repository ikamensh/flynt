import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "flynt" / "_git_version.py"


@pytest.mark.skip(reason="requires hatchling build and is not part of normal CI")
def test_git_version_written(tmp_path):
    """Ensure the build hook writes ``_git_version.py``.

    Prior versions of this test invoked the ``hatchling`` binary directly which
    failed when the executable was unavailable on PATH. Here we call the module
    via ``python -m hatchling`` and only run the test manually because it
    performs a full build and is relatively slow.
    """
    if VERSION_FILE.exists():
        VERSION_FILE.unlink()

    subprocess.check_call(
        [sys.executable, "-m", "hatchling", "build", "--hooks-only"], cwd=ROOT
    )
    assert VERSION_FILE.exists(), "version file should be generated"
    VERSION_FILE.unlink()
