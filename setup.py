
import ast
import re
import sys

import config
config.add_src_to_path()

assert sys.version_info >= (3, 6, 0), "flint requires Python 3.6+"
from pathlib import Path
from setuptools import setup

BASE_DIR = Path(__file__).parent


# forked from black's setup.py
def get_long_description():
    """Load README for long description"""
    readme_md = BASE_DIR / "README.md"
    with open(readme_md, encoding="utf8") as readme_f:
        return readme_f.read()


# forked from black's setup.py
# def get_version():
#     """Use a regex to pull out the version"""
#     flint_py = BASE_DIR / "src/flint/__init__.py"
#     _version_re = re.compile(r"__version__\s+=\s+(?P<version>.*)")
#     with open(flint_py, "r", encoding="utf8") as f:
#         match = _version_re.search(f.read())
#         version = match.group("version") if match is not None else '"unknown"'
#     return str(ast.literal_eval(version))


def get_requirements():
    with open("requirements.txt") as fp:
        return fp.read()


VERSION = '0.01'

setup(
    name="flint",
    packages=["src/flint"],
    version=VERSION,
    description="CLI tool to convert a python project's %-formatted strings to f-strings.",
    author="Hackathon Team",
    keywords=["utility", "strings"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
    license="GNU General Public License v3.0",
    long_description=get_long_description(),
    install_requires=get_requirements(),
    entry_points={"console_scripts": ["flint=src.flint:main"]},

)