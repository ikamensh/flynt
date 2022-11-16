import pytest

from flynt.state import _reset


@pytest.fixture(autouse=True)
def reset_state():
    """
    Fixture to reset the global state between each test
    """
    _reset()
