"""Packaging invariants for the wheel's python shim (python/flynt/).

The shim ships alongside the native binary so that `python -m flynt` keeps
working (as in 1.x) and `import flynt` explains the API removal instead of
raising a bare ModuleNotFoundError. These tests pin:
  * version consistency: Cargo.toml == harness VERSION, and the shim's
    __version__ is its PEP 440 normalization (maturin normalizes the same way
    for the wheel metadata) — so a release bump can't leave one behind;
  * the shim's import behavior, loaded straight from source (no install).
"""

import importlib.util
import re

import pytest

from conftest import REPO_DIR

SHIM_DIR = REPO_DIR / "python" / "flynt"


def cargo_version() -> str:
    text = (REPO_DIR / "Cargo.toml").read_text(encoding="utf-8")
    return re.search(r'^version = "([^"]+)"', text, re.M).group(1)


def pep440(cargo: str) -> str:
    """2.0.0-beta.1 -> 2.0.0b1 (the normalization maturin applies)."""
    return re.sub(
        r"-(alpha|beta|rc)\.(\d+)$",
        lambda m: {"alpha": "a", "beta": "b", "rc": "rc"}[m.group(1)] + m.group(2),
        cargo,
    )


def load_shim():
    spec = importlib.util.spec_from_file_location("flynt_shim", SHIM_DIR / "__init__.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_versions_in_sync():
    from test_cli_binary import VERSION

    assert cargo_version() == VERSION
    assert load_shim().__version__ == pep440(cargo_version())


def test_shim_import_is_benign_but_attributes_raise():
    # `python -m flynt` imports the package first, so import itself must not
    # raise; API access must fail loudly with migration guidance.
    mod = load_shim()
    with pytest.raises(AttributeError, match="flynt<2"):
        mod.main
    with pytest.raises(AttributeError, match="no attribute 'api'"):
        mod.api


def test_main_shim_compiles():
    source = (SHIM_DIR / "__main__.py").read_text(encoding="utf-8")
    compile(source, str(SHIM_DIR / "__main__.py"), "exec")
