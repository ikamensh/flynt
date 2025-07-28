import json
import os
import shutil


from flynt.api import _fstringify_file
from flynt.state import State


def test_sample_notebook(tmp_path):
    """Integration test for notebook conversion.

    Ensures that with ``process_notebooks`` enabled only code cells are
    transformed, while markdown cells and already f-string formatted code stay
    untouched.
    """
    folder = os.path.dirname(__file__)
    src = os.path.join(folder, "samples_in", "simple.ipynb")
    expected = os.path.join(folder, "expected_out", "simple.ipynb")
    nb_path = tmp_path / "simple.ipynb"
    shutil.copy2(src, nb_path)

    result = _fstringify_file(str(nb_path), State(process_notebooks=True))
    assert result and result.n_changes == 1

    with open(nb_path) as f:
        converted = json.load(f)
    with open(expected) as f:
        expect = json.load(f)

    assert converted == expect
