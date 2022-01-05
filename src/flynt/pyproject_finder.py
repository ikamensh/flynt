"""Content of this file is heavily inspired by source code of black, some sections are copied.
https://github.com/psf/black/
"""

import sys
from functools import lru_cache
from pathlib import Path
import os
from typing import Tuple, Optional, Dict, Any, Sequence

import tomli
from black import err


@lru_cache()
def find_project_root(srcs: Sequence[str]) -> Path:
    """Return a directory containing .git, .hg, or pyproject.toml.

    That directory will be a common parent of all files and directories
    passed in `srcs`.

    If no directory in the tree contains a marker that would specify it's the
    project root, the root of the file system is returned.
    """
    if not srcs:
        srcs = [str(Path.cwd().resolve())]

    path_srcs = [Path(Path.cwd(), src).resolve() for src in srcs]

    # A list of lists of parents for each 'src'. 'src' is included as a
    # "parent" of itself if it is a directory
    src_parents = [
        list(path.parents) + ([path] if path.is_dir() else []) for path in path_srcs
    ]

    common_base = max(
        set.intersection(*(set(parents) for parents in src_parents)),
        key=lambda path: path.parts,
    )

    for directory in (common_base, *common_base.parents):
        if (directory / ".git").exists():
            return directory

        if (directory / ".hg").is_dir():
            return directory

        if (directory / "pyproject.toml").is_file():
            return directory

    return directory


def find_pyproject_toml(path_search_start: Tuple[str, ...]) -> Optional[str]:
    """Find the absolute filepath to a pyproject.toml if it exists"""
    path_project_root = find_project_root(path_search_start)
    path_pyproject_toml = path_project_root / "pyproject.toml"
    if path_pyproject_toml.is_file():
        return str(path_pyproject_toml)

    try:
        path_user_pyproject_toml = find_user_pyproject_toml()
        return (
            str(path_user_pyproject_toml)
            if path_user_pyproject_toml.is_file()
            else None
        )
    except PermissionError as e:
        # We do not have access to the user-level config directory, so ignore it.
        err(f"Ignoring user configuration directory due to {e!r}")
        return None


def parse_pyproject_toml(path_config: str) -> Dict[str, Any]:
    """Parse a pyproject toml file, pulling out relevant parts for flynt

    If parsing fails, will raise a tomli.TOMLDecodeError
    """
    with open(path_config, encoding="utf8") as f:
        pyproject_toml = tomli.load(f)

    config = pyproject_toml.get("tool", {}).get("flynt", {})
    if path_config.endswith("flynt.toml"):
        config.update(pyproject_toml)

    return {k.replace("--", "").replace("-", "_"): v for k, v in config.items()}


@lru_cache()
def find_user_pyproject_toml() -> Path:
    r"""Return the path to the top-level user configuration for black.

    This looks for ~\.flynt on Windows and ~/.config/flynt on Linux and other
    Unix systems.
    """
    if sys.platform == "win32":
        # Windows
        user_config_path = Path.home() / ".flynt.toml"
    else:
        config_root = os.environ.get("XDG_CONFIG_HOME", "~/.config")
        user_config_path = Path(config_root).expanduser() / "flynt.toml"
    return user_config_path.resolve()
