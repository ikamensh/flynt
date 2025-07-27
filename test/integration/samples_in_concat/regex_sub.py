#!/usr/bin/env python3

import re


spam = "%s %s" % ("foo", "bar")

individual_tests = [
    re.sub(r"\.py$", "", test) + ".py" for test in ["a.py", "b.py", "c*"] if not test.endswith('*')
]

spam2 = "%s %s" % ("foo", "bar")

