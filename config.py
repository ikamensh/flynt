import sys
import os

VERSION = '0.02'

home = os.path.dirname(__file__)

print(sys.path)

def add_src_to_path():
    sys.path.append(home)
    sys.path.append(os.path.join(home, "src"))


