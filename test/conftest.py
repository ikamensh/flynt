import config
config.add_src_to_path()


import pytest
import os

int_test_dir = os.path.join(config.home, "test/integration/")

@pytest.fixture()
def two_liner_content():
    filepath = os.path.join(int_test_dir, "samples_in/two_liner.py")
    with open(filepath) as f:
        txt = f.read()

    yield txt


@pytest.fixture()
def two_liner_expected_output():
    filepath = os.path.join(int_test_dir, "expected_out/two_liner.py")

    with open(filepath) as f:
        txt = f.read()

    yield txt


@pytest.fixture()
def output_file():
    filepath = os.path.join(int_test_dir, "actual_out/two_liner.py")
    with open(filepath, 'w') as f:
        yield f