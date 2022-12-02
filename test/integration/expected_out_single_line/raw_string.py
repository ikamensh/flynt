def set_filename_version(filename, version_number, pattern):
    changed = []

    def inject_version(match):
        before, old, after = match.groups()
        changed.append(True)
        return before + version_number + after

    with open(filename, encoding="utf-8") as f:
        contents = re.sub(
            r"^(\s*%s\s*=\s*')(.+?)(')" % pattern,
            inject_version,
            f.read(),
            flags=re.DOTALL | re.MULTILINE,
        )
