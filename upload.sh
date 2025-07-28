#!/usr/bin/env bash

rm -r dist
python -m build .
python -m twine upload --repository-url https://upload.pypi.org/legacy/ dist/* -u __token__
