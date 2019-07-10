import sys

import config
config.add_src_to_path()
import flynt

VERSION = '0.17'

assert VERSION == flynt.__version__

assert sys.version_info >= (3, 7, 0), "flint requires Python 3.7+"
from pathlib import Path
from setuptools import setup

BASE_DIR = Path(__file__).parent


# forked from black's setup.py
def get_long_description():
    """Load README for long description"""
    readme_md = BASE_DIR / "README.md"
    with open(readme_md, encoding="utf8") as readme_f:
        return readme_f.read()


def get_requirements():
    with open("requirements.txt") as fp:
        return fp.read()

setup(
    name="flynt",
    packages=["flynt", "flynt.transform"],
    package_dir={'flynt': 'src/flynt', "flynt.transform": "src/flynt/transform"},
    version=VERSION,
    description="CLI tool to convert a python project's %-formatted strings to f-strings.",
    author="Hackathon Team",
    keywords=["utility", "strings"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
    license="GNU General Public License v3.0",
    # long_description=get_long_description(),
    long_description="CLI tool to convert a python project's .format(...) and %-formatted "
                     "strings to f-strings.",
    install_requires=get_requirements(),
    entry_points={"console_scripts": ["flynt=flynt:main"]},

)