try:
    import config
except ImportError:
    # assume remote server enters the application in tests/, home would be tests/..
    import sys
    import os

    test_dir = os.path.dirname(__file__)
    home = os.path.join(test_dir, os.path.pardir)

    sys.path.append(home)
    sys.path.append(os.path.join(home, "src"))
else:
    config.add_src_to_path()














