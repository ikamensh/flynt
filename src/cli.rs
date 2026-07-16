//! Port of src/flynt/cli.py. Owner: task #9 — except `run_harness_json`,
//! which is the stable machine interface used by the golden-file test
//! harness (harness/ directory) and must keep its protocol:
//!
//! stdin:  {"code": str, "pipeline": "fstring"|"concat"|"join",
//!          "state": {"multiline": bool, "len_limit": int|null,
//!                    "transform_percent": bool, "transform_format": bool,
//!                    "aggressive": int}}
//! stdout: {"out": str, "count": int}

use serde::Deserialize;

use crate::code_editor;
use crate::state::State;

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

/// Port of run_flynt_cli. Owner: task #9.
pub fn run(args: Vec<String>) -> i32 {
    if args.first().map(String::as_str) == Some("--harness-json") {
        return run_harness_json();
    }
    todo!("task #9: full CLI")
}
