import sys
import os

home = os.path.dirname(__file__)

print(sys.path)


def add_src_to_path():
    sys.path.append(home)
    sys.path.append(os.path.join(home, "src"))
