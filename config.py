import os
import sys

home = os.path.dirname(__file__)


def add_src_to_path():
    sys.path.append(home)
    sys.path.append(os.path.join(home, "src"))
