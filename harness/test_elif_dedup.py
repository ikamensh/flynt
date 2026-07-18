"""Regression: candidates in `elif` conditions must be collected exactly once.

ruff 0.14.11's `walk_stmt` visits an `elif` clause's test expression twice
(inline in the `StmtIf` arm, then again via `walk_elif_else_clause`). Before
the same-range dedup in chunk::sort_dedup, every pipeline collected such
candidates twice and applied the edit twice, producing corrupted output like
`elif f"{opt}="f"{opt}=" in possibilities:` — found by a corpus differential
against flynt 1.0.6 on cpython's Lib/getopt.py. These pin the fixed behavior
for all four pipelines at the binary level.
"""

import pytest

from conftest import run_pipeline

ELIF_CASES = [
    ("fstring", 'if a:\n    pass\nelif x == "%s!" % b:\n    pass\n',
     'if a:\n    pass\nelif x == f"{b}!":\n    pass\n'),
    ("fstring", 'if a:\n    pass\nelif x == "{}!".format(b):\n    pass\n',
     'if a:\n    pass\nelif x == f"{b}!":\n    pass\n'),
    ("concat", 'if a:\n    pass\nelif opt + "=" in ps:\n    pass\n',
     'if a:\n    pass\nelif f"{opt}=" in ps:\n    pass\n'),
    ("join", 'if a:\n    pass\nelif "_".join(["a", b]) == x:\n    pass\n',
     'if a:\n    pass\nelif f"a_{b}" == x:\n    pass\n'),
]


@pytest.mark.parametrize("pipeline, code, expected", ELIF_CASES)
def test_elif_condition_converted_exactly_once(pipeline, code, expected):
    out, count = run_pipeline(code, pipeline)
    assert out == expected
    assert count == 1


def test_elif_chain_each_condition_once():
    code = (
        'if a:\n    pass\n'
        'elif "%s" % b == x:\n    pass\n'
        'elif "%s" % c == y:\n    pass\n'
        'else:\n    d = "%s" % e\n'
    )
    out, count = run_pipeline(code)
    assert out == (
        'if a:\n    pass\n'
        'elif f"{b}" == x:\n    pass\n'
        'elif f"{c}" == y:\n    pass\n'
        'else:\n    d = f"{e}"\n'
    )
    assert count == 3
