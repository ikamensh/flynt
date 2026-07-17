//! End-to-end CLI tests driving the built binary, mirroring the capsys-based
//! assertions in flynt/test/integration/test_cli.py that do not require the
//! transform core (version, missing-src, invalid snippet, usage errors).

use std::process::Command;

fn flynt() -> Command {
    Command::new(env!("CARGO_BIN_EXE_flynt"))
}

// Port of test_cli.py::test_cli_version — prints only the version.
#[test]
fn version_prints_only_version() {
    let out = flynt().arg("--version").output().unwrap();
    assert_eq!(out.status.code(), Some(0));
    assert_eq!(
        String::from_utf8_lossy(&out.stdout),
        format!("{}\n", env!("CARGO_PKG_VERSION"))
    );
    assert!(out.stderr.is_empty());
}

// Port of test_cli.py::test_cli_no_args — requires src, returns 1.
#[test]
fn no_args_requires_src() {
    let out = flynt().output().unwrap();
    assert_eq!(out.status.code(), Some(1));
    let stdout = String::from_utf8_lossy(&out.stdout);
    assert!(stdout.contains("the following arguments are required: src"));
}

// Port of test_cli.py::test_cli_string_quoted invalid-snippet case — falls back
// to printing the input unchanged when it does not parse.
#[test]
fn string_invalid_snippet_echoes_input() {
    let snippet = "This ! isn't <> valid .. Python $ code";
    let out = flynt().args(["-s", snippet]).output().unwrap();
    assert_eq!(out.status.code(), Some(0));
    assert_eq!(String::from_utf8_lossy(&out.stdout).trim_end(), snippet);
    assert!(out.stderr.is_empty());
}

// Port of test_cli.py::test_cli_string_unquoted invalid case — args joined by
// spaces before conversion.
#[test]
fn string_unquoted_invalid_snippet_echoes_input() {
    let snippet = "This ! isn't <> valid .. Python $ code";
    let mut args = vec!["-s"];
    args.extend(snippet.split(' '));
    let out = flynt().args(&args).output().unwrap();
    assert_eq!(out.status.code(), Some(0));
    assert_eq!(String::from_utf8_lossy(&out.stdout).trim_end(), snippet);
}

// --stdout is incompatible with --verbose (argparse-style error, exit 2).
#[test]
fn stdout_with_verbose_exits_2() {
    let out = flynt().args(["--stdout", "-v", "x.py"]).output().unwrap();
    assert_eq!(out.status.code(), Some(2));
}
