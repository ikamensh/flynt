import os
import sys

__version__ = "0.45.5"

home = os.path.dirname(__file__)


def add_src_to_path():
    sys.path.append(home)
    sys.path.append(os.path.join(home, "src"))
