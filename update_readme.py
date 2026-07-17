"""Updates the README.md file with the latest help output from flynt.

Runs the Rust binary (builds it if needed): python update_readme.py
"""

import re
import subprocess
from pathlib import Path

options_marker = "<!-- begin-options -->"


def main():
    root = Path(__file__).parent
    subprocess.run(["cargo", "build", "--quiet"], cwd=root, check=True)
    flynt_help = subprocess.run(
        [root / "target" / "debug" / "flynt", "--help"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    readme_path = root / "README.md"
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
