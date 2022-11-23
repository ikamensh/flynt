"""
Updates the README.md file with the latest help output from flynt.
"""
import contextlib
import io
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

from flynt.cli import run_flynt_cli

options_marker = "<!-- begin-options -->"


def patch_terminal_size():
    """
    Patch the terminal size to 70 characters
    for better wrapping of help output.
    """
    return patch(
        "shutil.get_terminal_size",
        return_value=os.terminal_size((70, 24)),
    )


def main():
    readme_path = Path(__file__).parent / "README.md"
    sio = io.StringIO()
    # Redirect the output,
    # disable argparse exiting the entire program when it prints help,
    # and patch the terminal size so we get the same output all the time
    with contextlib.redirect_stdout(sio), contextlib.suppress(
        SystemExit
    ), patch_terminal_size():
        sys.argv = ["flynt", "--help"]
        run_flynt_cli()
    flynt_help = sio.getvalue()
    original_readme_content = readme_path.read_text()
    readme_content = re.sub(
        rf"{options_marker}\n```.+?```\n",
        f"{options_marker}\n```\n{flynt_help}\n```\n",
        original_readme_content,
        flags=re.DOTALL,
    )
    if readme_content != original_readme_content:
        readme_path.write_text(readme_content)
        print("Updated README.md")


if __name__ == "__main__":
    main()
