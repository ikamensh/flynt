import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "flynt" / "_git_version.py"


def test_git_version_written(tmp_path):
    """The build hook should write _git_version.py during a build.

    This verifies that version information from git gets materialized when
    running ``hatchling build --hooks-only``. The file is cleaned up afterwards
    so the repository state is not modified by the test.
    """
    if VERSION_FILE.exists():
        VERSION_FILE.unlink()

    subprocess.check_call(["hatchling", "build", "--hooks-only"], cwd=ROOT)
    assert VERSION_FILE.exists(), "version file should be generated"

    VERSION_FILE.unlink()
