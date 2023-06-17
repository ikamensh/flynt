import pytest

from flynt.state import State


@pytest.fixture
def state() -> State:
    """
    Fixture for a default state object
    """
    return State()
