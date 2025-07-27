#!/usr/bin/env python3

import re


spam = f"foo bar"

individual_tests = [
    re.sub(r"\.py$", "", test) + ".py" for test in ["a.py", "b.py", "c*"] if not test.endswith('*')
]

spam2 = f"foo bar"

