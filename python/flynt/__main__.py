"""`python -m flynt` runs the bundled native binary (same CLI as `flynt`)."""

import os
import sys
import sysconfig


def _flynt_bin() -> str:
    exe = "flynt" + (sysconfig.get_config_var("EXE") or "")
    path = os.path.join(sysconfig.get_path("scripts"), exe)
    if os.path.isfile(path):
        return path
    # `pip install --user` puts scripts in the user scheme, not next to python.
    if sys.version_info >= (3, 10):
        user_scheme = sysconfig.get_preferred_scheme("user")
    elif os.name == "nt":
        user_scheme = "nt_user"
    elif sys.platform == "darwin" and getattr(sys, "_framework", None):
        user_scheme = "osx_framework_user"
    else:
        user_scheme = "posix_user"
    user_path = os.path.join(sysconfig.get_path("scripts", scheme=user_scheme), exe)
    if os.path.isfile(user_path):
        return user_path
    raise FileNotFoundError(path)


if __name__ == "__main__":
    flynt = _flynt_bin()
    argv = [flynt, *sys.argv[1:]]
    if sys.platform == "win32":
        import subprocess

        sys.exit(subprocess.run(argv).returncode)
    else:
        os.execv(flynt, argv)
