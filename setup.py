import re
from pathlib import Path

from setuptools import setup

_DIR = Path(__file__).parent


with (_DIR / "src/flynt/__init__.py").open() as f:
    version = re.search('__version__ = "(.*?)"', f.read()).group(1)


def get_requirements():
    with (_DIR / "requirements.txt").open() as f:
        return f.read()


setup(
    name="flynt",
    packages=["flynt", "flynt.transform", "flynt.lexer", "flynt.string_concat", "flynt.linting"],
    package_dir={"": "src"},
    version=version,
    description="CLI tool to convert a python project's %-formatted strings "
    "to f-strings.",
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
    long_description=(_DIR / "README.md").read_text().strip(),
    long_description_content_type="text/markdown",
    install_requires=get_requirements(),
    python_requires=">=3.6",
    entry_points={"console_scripts": ["flynt=flynt:main"]},
    url="https://github.com/ikamensh/flynt",
    include_package_data=True,
)
