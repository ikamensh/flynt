from flynt.pyproject_finder import find_pyproject_toml, parse_pyproject_toml
import os

pyproject_content = """
[tool.flynt]
verbose = true
line_length = 120
"""


other_tool_config = """
[tool.mypy]
verbose = true
"""


def test_finds_config(tmpdir):
    """Given file structure:
    -pyproject.toml
    -src
    --foo.py

    the pyproject config should be used for `flynt src/foo.py` command.
    """
    path = tmpdir / "pyproject.toml"
    with open(path, "w") as f:
        f.write(pyproject_content)

    src = tmpdir / "src"
    os.makedirs(src)
    pyfile = src / "foo.py"
    pyfile_path_str = str(pyfile)

    cfg_file = find_pyproject_toml((pyfile_path_str,))
    d = parse_pyproject_toml(cfg_file)
    assert d["verbose"] == True
    assert d["line_length"] == 120


def test_ignores_irrelevant_config(tmpdir):
    """Keys in the config that are in other tools sections should not be parsed. """
    path = tmpdir / "pyproject.toml"
    with open(path, "w") as f:
        f.write(other_tool_config)

    src = tmpdir / "src"
    os.makedirs(src)
    pyfile = src / "foo.py"
    pyfile_path_str = str(pyfile)

    cfg_file = find_pyproject_toml((pyfile_path_str,))
    d = parse_pyproject_toml(cfg_file)
    assert not d


def test_ignores_subfolder_config(tmpdir):
    """Given file structure:
    -otherproj
    --pyproject.toml
    -src
    --foo.py

    the pyproject config should NOT be used for `flynt src/foo.py` command.
    """

    other_proj = tmpdir / "other_proj"
    cfg_path = other_proj / "pyproject.toml"
    os.makedirs(other_proj)

    with open(cfg_path, "w") as f:
        f.write(pyproject_content)

    src = tmpdir / "src"
    os.makedirs(src)
    pyfile = src / "foo.py"
    pyfile_path_str = str(pyfile)

    cfg_file = find_pyproject_toml((pyfile_path_str,))
    assert cfg_file is None
