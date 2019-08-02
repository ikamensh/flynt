import re

import config
config.add_src_to_path()

with open("src/flynt/__init__.py") as f:
    version = re.search('__version__ = "(.*?)"', f.read()).group(1)

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
    packages=["flynt", "flynt.transform", "flynt.lexer"],
    package_dir={'': 'src'},
    version=version,
    description="CLI tool to convert a python project's %-formatted strings to f-strings.",
    author="Ilya Kamenshchikov",
    keywords=["utility", "strings"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
    license="MIT",
    # long_description=get_long_description(),
    long_description="CLI tool to convert a python project's .format(...) and %-formatted "
                     "strings to f-strings.",
    install_requires=get_requirements(),
    python_requires=">=3.6",
    entry_points={"console_scripts": ["flynt=flynt:main"]},
    url="https://github.com/ikamensh/flynt",
)
