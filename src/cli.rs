//! Port of src/flynt/cli.py. Owner: task #9 — except `run_harness_json`,
//! which is the stable machine interface used by the golden-file test
//! harness (harness/ directory) and must keep its protocol:
//!
//! stdin:  {"code": str, "pipeline": "fstring"|"concat"|"join",
//!          "state": {"multiline": bool, "len_limit": int|null,
//!                    "transform_percent": bool, "transform_format": bool,
//!                    "aggressive": int}}
//! stdout: {"out": str, "count": int}

use std::collections::{HashMap, HashSet};

use serde::Deserialize;

use crate::code_editor;
use crate::state::State;
use crate::{api, pyproject};

#[derive(Deserialize)]
struct HarnessState {
    #[serde(default = "default_true")]
    multiline: bool,
    #[serde(default)]
    len_limit: Option<usize>,
    #[serde(default = "default_true")]
    transform_percent: bool,
    #[serde(default = "default_true")]
    transform_format: bool,
    #[serde(default)]
    aggressive: u8,
}

fn default_true() -> bool {
    true
}

#[derive(Deserialize)]
struct HarnessRequest {
    code: String,
    pipeline: String,
    state: HarnessState,
}

/// Machine interface for the pytest golden-file harness.
pub fn run_harness_json() -> i32 {
    let mut input = String::new();
    use std::io::Read;
    std::io::stdin().read_to_string(&mut input).expect("read stdin");
    let req: HarnessRequest = serde_json::from_str(&input).expect("bad harness request");

    let mut state = State {
        multiline: req.state.multiline,
        len_limit: req.state.len_limit,
        transform_percent: req.state.transform_percent,
        transform_format: req.state.transform_format,
        aggressive: req.state.aggressive,
        ..State::default()
    }
    .finalize();
    // Mirror Python tests: State(multiline=False, len_limit=None, ...) still
    // gets len_limit=0 via __post_init__; explicit len_limit in the request
    // wins only when multiline is true.

    let (out, count) = match req.pipeline.as_str() {
        "fstring" => code_editor::fstringify_code_by_line(&req.code, &mut state),
        "concat" => code_editor::fstringify_concats(&req.code, &mut state),
        "join" => code_editor::fstringify_static_joins(&req.code, &mut state),
        other => panic!("unknown pipeline: {other}"),
    };
    let resp = serde_json::json!({ "out": out, "count": count });
    println!("{resp}");
    0
}

/// Parsed command-line arguments (subset of argparse's namespace that flynt
/// uses). `explicit` records which option dests the user set, so pyproject
/// config values only fill in unset defaults (CLI overrides config).
#[derive(Debug)]
struct Args {
    verbose: u32,
    quiet: bool,
    no_multiline: bool,
    line_length: i64,
    dry_run: bool,
    stdout: bool,
    string: bool,
    transform_percent: bool,
    transform_format: bool,
    transform_concats: bool,
    transform_joins: bool,
    fail_on_change: bool,
    aggressive: u8,
    exclude: Option<Vec<String>>,
    notebook: bool,
    src: Vec<String>,
    version: bool,
    report: bool,
    explicit: HashSet<&'static str>,
}

impl Default for Args {
    fn default() -> Self {
        Self {
            verbose: 0,
            quiet: false,
            no_multiline: false,
            line_length: 88,
            dry_run: false,
            stdout: false,
            string: false,
            transform_percent: true,
            transform_format: true,
            transform_concats: false,
            transform_joins: false,
            fail_on_change: false,
            aggressive: 0,
            exclude: None,
            notebook: false,
            src: Vec::new(),
            version: false,
            report: false,
            explicit: HashSet::new(),
        }
    }
}

fn is_option(tok: &str) -> bool {
    tok.starts_with('-') && tok != "-"
}

/// Hand-rolled parser covering the flags flynt's tests exercise. Returns
/// `Err(code)` for argparse-style usage errors (exit 2).
fn parse_args(argv: &[String]) -> Result<Args, i32> {
    let mut a = Args::default();
    let mut i = 0;
    while i < argv.len() {
        let tok = &argv[i];
        if tok == "-" {
            a.src.push(tok.clone());
            i += 1;
            continue;
        }
        if let Some(long) = tok.strip_prefix("--") {
            let (name, inline_val) = match long.split_once('=') {
                Some((n, v)) => (n, Some(v.to_string())),
                None => (long, None),
            };
            match name {
                "verbose" => {
                    a.verbose += 1;
                    a.explicit.insert("verbose");
                }
                "quiet" => {
                    a.quiet = true;
                    a.explicit.insert("quiet");
                }
                "no-multiline" => {
                    a.no_multiline = true;
                    a.explicit.insert("no_multiline");
                }
                "line-length" => {
                    let v = take_value(inline_val, argv, &mut i)?;
                    a.line_length = v.parse().map_err(|_| 2)?;
                    a.explicit.insert("line_length");
                }
                "dry-run" => {
                    a.dry_run = true;
                    a.explicit.insert("dry_run");
                }
                "stdout" => {
                    a.stdout = true;
                    a.explicit.insert("stdout");
                }
                "string" => {
                    a.string = true;
                    a.explicit.insert("string");
                }
                "no-tp" | "no-transform-percent" => {
                    a.transform_percent = false;
                    a.explicit.insert("transform_percent");
                }
                "no-tf" | "no-transform-format" => {
                    a.transform_format = false;
                    a.explicit.insert("transform_format");
                }
                "transform-concats" => {
                    a.transform_concats = true;
                    a.explicit.insert("transform_concats");
                }
                "transform-joins" => {
                    a.transform_joins = true;
                    a.explicit.insert("transform_joins");
                }
                "fail-on-change" => {
                    a.fail_on_change = true;
                    a.explicit.insert("fail_on_change");
                }
                "aggressive" => {
                    a.aggressive += 1;
                    a.explicit.insert("aggressive");
                }
                "exclude" => {
                    let mut vals = Vec::new();
                    if let Some(v) = inline_val {
                        vals.push(v);
                    }
                    while i + 1 < argv.len() && !is_option(&argv[i + 1]) {
                        i += 1;
                        vals.push(argv[i].clone());
                    }
                    a.exclude = Some(vals);
                    a.explicit.insert("exclude");
                }
                "notebook" => {
                    a.notebook = true;
                    a.explicit.insert("notebook");
                }
                "version" => a.version = true,
                "report" => {
                    a.report = true;
                    a.explicit.insert("report");
                }
                _ => {
                    eprintln!("flynt: error: unrecognized arguments: {tok}");
                    return Err(2);
                }
            }
            i += 1;
            continue;
        }
        if is_option(tok) {
            let s = &tok[1..];
            match s {
                "v" => bump(&mut a.verbose, &mut a.explicit, "verbose"),
                "q" => {
                    a.quiet = true;
                    a.explicit.insert("quiet");
                }
                "d" => {
                    a.dry_run = true;
                    a.explicit.insert("dry_run");
                }
                "s" => {
                    a.string = true;
                    a.explicit.insert("string");
                }
                "f" => {
                    a.fail_on_change = true;
                    a.explicit.insert("fail_on_change");
                }
                "a" => bump8(&mut a.aggressive, &mut a.explicit, "aggressive"),
                "ll" => {
                    let v = take_value(None, argv, &mut i)?;
                    a.line_length = v.parse().map_err(|_| 2)?;
                    a.explicit.insert("line_length");
                }
                "tc" => {
                    a.transform_concats = true;
                    a.explicit.insert("transform_concats");
                }
                "tj" => {
                    a.transform_joins = true;
                    a.explicit.insert("transform_joins");
                }
                "nb" => {
                    a.notebook = true;
                    a.explicit.insert("notebook");
                }
                "e" => {
                    let mut vals = Vec::new();
                    while i + 1 < argv.len() && !is_option(&argv[i + 1]) {
                        i += 1;
                        vals.push(argv[i].clone());
                    }
                    if vals.is_empty() {
                        return Err(2);
                    }
                    a.exclude = Some(vals);
                    a.explicit.insert("exclude");
                }
                _ if s.chars().all(|c| c == 'v') => {
                    a.verbose += s.len() as u32;
                    a.explicit.insert("verbose");
                }
                _ if s.chars().all(|c| c == 'a') => {
                    a.aggressive += s.len() as u8;
                    a.explicit.insert("aggressive");
                }
                _ if s.starts_with("ll") => {
                    a.line_length = s[2..].parse().map_err(|_| 2)?;
                    a.explicit.insert("line_length");
                }
                _ => {
                    eprintln!("flynt: error: unrecognized arguments: {tok}");
                    return Err(2);
                }
            }
            i += 1;
            continue;
        }
        a.src.push(tok.clone());
        i += 1;
    }
    Ok(a)
}

// Small helpers to keep the long-option arm terse.
fn bump(count: &mut u32, explicit: &mut HashSet<&'static str>, key: &'static str) {
    *count += 1;
    explicit.insert(key);
}
fn bump8(count: &mut u8, explicit: &mut HashSet<&'static str>, key: &'static str) {
    *count += 1;
    explicit.insert(key);
}
fn take_value(
    inline: Option<String>,
    argv: &[String],
    i: &mut usize,
) -> Result<String, i32> {
    match inline {
        Some(v) => Ok(v),
        None => {
            *i += 1;
            argv.get(*i).cloned().ok_or(2)
        }
    }
}

fn strip_linesep(s: &str) -> String {
    let n = LINESEP.chars().count();
    let total = s.chars().count();
    if total < n {
        return String::new();
    }
    s.chars().take(total - n).collect()
}

#[cfg(windows)]
const LINESEP: &str = "\r\n";
#[cfg(not(windows))]
const LINESEP: &str = "\n";

fn state_from_args(a: &Args) -> State {
    State {
        aggressive: a.aggressive,
        dry_run: a.dry_run,
        stdout: a.stdout,
        len_limit: Some(a.line_length.max(0) as usize),
        multiline: !a.no_multiline,
        quiet: a.quiet || a.stdout,
        transform_concat: a.transform_concats,
        transform_format: a.transform_format,
        transform_join: a.transform_joins,
        transform_percent: a.transform_percent,
        report: a.report,
        process_notebooks: a.notebook,
        ..State::default()
    }
    .finalize()
}

fn supported_arg_names() -> Vec<&'static str> {
    vec![
        "verbose",
        "quiet",
        "no_multiline",
        "line_length",
        "dry_run",
        "stdout",
        "string",
        "transform_percent",
        "transform_format",
        "transform_concats",
        "transform_joins",
        "fail_on_change",
        "aggressive",
        "exclude",
        "notebook",
        "src",
        "version",
        "report",
    ]
}

fn warn_unknown_config(cfg: &HashMap<String, toml::Value>) {
    let supported: HashSet<&str> = supported_arg_names().into_iter().collect();
    let mut redundant: Vec<&String> = cfg
        .keys()
        .filter(|k| !supported.contains(k.as_str()))
        .collect();
    if !redundant.is_empty() {
        redundant.sort();
        let mut sup = supported_arg_names();
        sup.sort();
        eprintln!(
            "Unknown config options: {redundant:?}. This might be a spelling problem. \
             Supported options are: {sup:?}"
        );
    }
}

fn apply_config_defaults(a: &mut Args, cfg: &HashMap<String, toml::Value>) {
    for (k, v) in cfg {
        if a.explicit.contains(k.as_str()) {
            continue;
        }
        match k.as_str() {
            "verbose" => {
                if let Some(b) = v.as_bool() {
                    a.verbose = u32::from(b);
                } else if let Some(n) = v.as_integer() {
                    a.verbose = n.max(0) as u32;
                }
            }
            "quiet" => set_bool(&mut a.quiet, v),
            "no_multiline" => set_bool(&mut a.no_multiline, v),
            "line_length" => {
                if let Some(n) = v.as_integer() {
                    a.line_length = n;
                }
            }
            "dry_run" => set_bool(&mut a.dry_run, v),
            "stdout" => set_bool(&mut a.stdout, v),
            "string" => set_bool(&mut a.string, v),
            "transform_percent" => set_bool(&mut a.transform_percent, v),
            "transform_format" => set_bool(&mut a.transform_format, v),
            "transform_concats" => set_bool(&mut a.transform_concats, v),
            "transform_joins" => set_bool(&mut a.transform_joins, v),
            "fail_on_change" => set_bool(&mut a.fail_on_change, v),
            "aggressive" => {
                if let Some(n) = v.as_integer() {
                    a.aggressive = n.max(0) as u8;
                }
            }
            "notebook" => set_bool(&mut a.notebook, v),
            "report" => set_bool(&mut a.report, v),
            "exclude" => {
                if let Some(arr) = v.as_array() {
                    a.exclude = Some(
                        arr.iter()
                            .filter_map(|x| x.as_str().map(String::from))
                            .collect(),
                    );
                }
            }
            _ => {}
        }
    }
}

fn set_bool(dst: &mut bool, v: &toml::Value) {
    if let Some(b) = v.as_bool() {
        *dst = b;
    }
}

fn print_usage() {
    println!(
        "usage: flynt [-h] [-v | -q] [--no-multiline | -ll LINE_LENGTH] \
         [-d | --stdout] [-s] [--no-tp] [--no-tf] [-tc] [-tj] [-f] [-a] \
         [-e EXCLUDE [EXCLUDE ...]] [-nb] [--version] [--report] [src ...]"
    );
}

/// Port of run_flynt_cli. Owner: task #9. Keeps the `--harness-json` machine
/// interface dispatch intact.
pub fn run(args: Vec<String>) -> i32 {
    if args.first().map(String::as_str) == Some("--harness-json") {
        return run_harness_json();
    }

    let mut parsed = match parse_args(&args) {
        Ok(a) => a,
        Err(code) => return code,
    };

    if parsed.stdout && parsed.verbose > 0 {
        eprintln!("flynt: error: --stdout should not be used with -v/--verbose");
        return 2;
    }

    if parsed.version {
        println!("{}", crate::VERSION);
        return 0;
    }
    if parsed.src.is_empty() {
        println!("flynt: error: the following arguments are required: src");
        print_usage();
        return 1;
    }

    let mut state = state_from_args(&parsed);

    if parsed.string {
        let content = parsed.src.join(" ");
        match api::fstringify_code(&content, &mut state, "<code>") {
            Some(r) => println!("{}", r.content),
            None => println!("{content}"),
        }
        return 0;
    }

    if parsed.src.iter().any(|s| s == "-") {
        if parsed.src.len() > 1 {
            eprintln!("flynt: error: Cannot use '-' with a list of other paths");
            return 2;
        }
        let mut input = String::new();
        use std::io::Read;
        std::io::stdin().read_to_string(&mut input).expect("read stdin");
        let trimmed = strip_linesep(&input);
        return match api::fstringify_code(&trimmed, &mut state, "<stdin>") {
            Some(r) => {
                println!("{}", r.content);
                0
            }
            None => 1,
        };
    }

    let mut salutation = format!("Running flynt v.{}", crate::VERSION);
    if let Some(toml_file) = pyproject::find_pyproject_toml(&parsed.src) {
        salutation.push_str(&format!("\nUsing config file at {}", toml_file.display()));
        let cfg = pyproject::parse_pyproject_toml(&toml_file);
        warn_unknown_config(&cfg);
        apply_config_defaults(&mut parsed, &cfg);
        state = state_from_args(&parsed);
    }
    if !state.quiet {
        println!("{salutation}");
    }
    if parsed.verbose > 0 {
        println!("Using following options: {parsed:?}");
    }
    if parsed.dry_run {
        println!("Running flynt in dry-run mode. No files will be changed.");
    }
    api::fstringify(
        &parsed.src,
        parsed.exclude.as_deref(),
        parsed.fail_on_change,
        &mut state,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn run_args(v: &[&str]) -> i32 {
        run(v.iter().map(|s| s.to_string()).collect())
    }

    // Port of test_cli.py::test_cli_no_args.
    #[test]
    fn no_args_returns_1() {
        assert_eq!(run_args(&[]), 1);
    }

    // Port of test_cli.py::test_cli_version.
    #[test]
    fn version_returns_0() {
        assert_eq!(run_args(&["--version"]), 0);
    }

    // --stdout with -v is an argparse-style error (exit 2).
    #[test]
    fn stdout_with_verbose_is_error() {
        assert_eq!(run_args(&["--stdout", "-v", "x.py"]), 2);
    }

    // '-' cannot be combined with other paths (exit 2).
    #[test]
    fn stdin_dash_with_other_paths_is_error() {
        assert_eq!(run_args(&["-", "other.py"]), 2);
    }

    // Port of test_cli.py invalid-snippet case (no core needed: parse fails).
    #[test]
    fn string_invalid_snippet_returns_input() {
        assert_eq!(run_args(&["-s", "This ! isn't <> valid .. Python $ code"]), 0);
    }

    #[test]
    fn strip_linesep_removes_trailing_sep() {
        assert_eq!(strip_linesep("hello\n"), "hello".to_string());
        assert_eq!(strip_linesep("x"), String::new());
        assert_eq!(strip_linesep(""), String::new());
    }

    #[test]
    fn parse_collects_flags_and_src() {
        let a = parse_args(&[
            "-tc".into(),
            "--string".into(),
            "code".into(),
            "here".into(),
        ])
        .unwrap();
        assert!(a.transform_concats);
        assert!(a.string);
        assert_eq!(a.src, vec!["code".to_string(), "here".to_string()]);
    }

    #[test]
    fn parse_verbose_count_and_line_length() {
        let a = parse_args(&["-vv".into(), "-ll".into(), "72".into(), "f.py".into()]).unwrap();
        assert_eq!(a.verbose, 2);
        assert_eq!(a.line_length, 72);
        assert_eq!(a.src, vec!["f.py".to_string()]);
    }

    #[test]
    fn no_multiline_sets_len_limit_zero() {
        let a = parse_args(&["--no-multiline".into(), "f.py".into()]).unwrap();
        let state = state_from_args(&a);
        assert_eq!(state.len_limit, Some(0));
    }

    #[test]
    fn config_defaults_dont_override_explicit() {
        let mut a = parse_args(&["-ll".into(), "50".into(), "f.py".into()]).unwrap();
        let mut cfg = HashMap::new();
        cfg.insert("line_length".to_string(), toml::Value::Integer(120));
        cfg.insert("verbose".to_string(), toml::Value::Boolean(true));
        apply_config_defaults(&mut a, &cfg);
        assert_eq!(a.line_length, 50, "explicit CLI value must win");
        assert_eq!(a.verbose, 1, "config fills unset default");
    }
}
