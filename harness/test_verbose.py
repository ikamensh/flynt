"""The 2.0 verbose ladder (redesigned vs 1.x — see DIVERGENCES.md #7).

-v  : effective options line, modified files, and located refusal
      diagnostics (`file:line: reason` — 1.x printed reasons with no location).
-vv : additionally lists files scanned without changes.
The line-length diagnostic reports the actual -ll value that would allow the
conversion (1.x printed a literal '999 is an example' placeholder).
Default output stays exactly as before (pinned by the golden suite).
"""

from test_cli_binary import run_cli


def make_tree(tmp_path):
    (tmp_path / "ok.py").write_text('a = "%s" % x\n', encoding="utf-8")
    # %d without -a is refused with a stable, meaningful reason.
    (tmp_path / "refused.py").write_text('b = "%d" % n\n', encoding="utf-8")
    (tmp_path / "plain.py").write_text("c = 1\n", encoding="utf-8")


def test_v_lists_modified_and_located_diagnostics(tmp_path):
    make_tree(tmp_path)
    out = run_cli(["-v", str(tmp_path)]).stdout
    assert "Using options: " in out
    assert "explicit" not in out, "internal parser bookkeeping must not leak"
    assert "ok.py...modified" in out
    assert "refused.py:1: Skipping %d formatting" in out
    assert "plain.py" not in out, "-v hides scanned-but-unchanged files"
    assert "Namespace(" not in out and "Args {" not in out


def test_vv_adds_unchanged_files(tmp_path):
    make_tree(tmp_path)
    out = run_cli(["-vv", str(tmp_path)]).stdout
    assert "plain.py...no change" in out


def test_default_output_has_no_verbose_lines(tmp_path):
    make_tree(tmp_path)
    out = run_cli([str(tmp_path)]).stdout
    assert "fstringifying" not in out
    assert ":1:" not in out


def test_line_length_diag_reports_real_ll_value(tmp_path):
    # Converted form is `abc = f"{x} {y}"` (16 chars incl. the 6-char indent
    # of column 0... the chunk starts at col 6), so -ll 10 refuses it and the
    # diagnostic must name 16 — the smallest limit that would convert.
    (tmp_path / "long.py").write_text(
        'abc = "{} {}".format(\n    x,\n    y,\n)\n', encoding="utf-8"
    )
    out = run_cli(["-v", "-ll", "10", str(tmp_path)]).stdout
    assert "long.py:1: Skipping conversion of" in out
    assert "line length limit 10" in out
    assert "pass -ll 16 to convert it" in out
    # And the suggested value is truly sufficient:
    out2 = run_cli(["-v", "-ll", "16", str(tmp_path)]).stdout
    assert "long.py...modified" in out2


def test_quiet_suppresses_verbose_from_config(tmp_path):
    # verbose via config + --quiet on the CLI: quiet wins for file lines.
    (tmp_path / "pyproject.toml").write_text(
        "[tool.flynt]\nverbose = true\n", encoding="utf-8"
    )
    (tmp_path / "ok.py").write_text('a = "%s" % x\n', encoding="utf-8")
    out = run_cli(["-q", str(tmp_path)]).stdout
    assert "fstringifying" not in out
