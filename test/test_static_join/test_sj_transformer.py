import sys
from typing import Optional

import pytest

from flynt.static_join.transformer import transform_join
from test.test_static_join.utils import CASES

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 8), reason="requires python3.8 or higher"
)


@pytest.mark.parametrize("source, expected", CASES)
def test_transform(source: str, expected: Optional[str]):
    new, changed = transform_join(source)
    if changed:
        assert new == expected
    else:
        assert expected is None
