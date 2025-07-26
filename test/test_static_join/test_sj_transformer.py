import ast
import sys
from test.test_static_join.utils import CASES
from typing import Optional

import pytest

from flynt.static_join.transformer import transform_join

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 9), reason="requires python3.9 or higher"
)


@pytest.mark.parametrize("source, expected", CASES)
def test_transform(source: str, expected: Optional[str]):
    new, changed = transform_join(ast.parse(source))
    if changed:
        assert new == expected
    else:
        assert expected is None
