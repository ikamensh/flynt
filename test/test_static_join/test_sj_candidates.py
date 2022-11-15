import ast
import sys
from typing import Tuple

import pytest

from flynt.static_join.candidates import JoinHound, join_candidates
from test.test_static_join.utils import CASES

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 8), reason="requires python3.8 or higher"
)


@pytest.fixture()
def code_and_ok() -> Tuple[str, int]:
    """
    Fixture for generating a Python module from the test cases.
    """
    code = "\n".join(f"case{i} = {case}" for (i, (case, expected)) in enumerate(CASES))
    expected_ok = len([expected for (case, expected) in CASES if expected is not None])
    return code, expected_ok


@pytest.mark.parametrize("method", ["hound", "api"])
def test_find_victims(code_and_ok: Tuple[str, int], method: str):
    code, expected_ok = code_and_ok
    if method == "hound":
        tree = ast.parse(code)
        ch = JoinHound()
        ch.visit(tree)
        victims = ch.victims
    elif method == "api":
        victims = list(join_candidates(code))
    else:
        raise NotImplementedError("...")
    assert len(victims) == expected_ok
    assert all(".join" in str(v) for v in victims)
