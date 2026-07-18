//! flynt-rs: Rust port of flynt (https://github.com/ikamensh/flynt).
//!
//! Converts old-style `%` formatting and `.format()` calls in Python source
//! to f-strings, editing files in place while preserving all surrounding code.
//!
//! Module map (Python source file each module ports):
//! - `state`        <- src/flynt/state.py
//! - `error`        <- src/flynt/exceptions.py
//! - `chunk`        <- src/flynt/candidates/ast_chunk.py
//! - `quotes`       <- src/flynt/utils/format.py
//! - `astutils`     <- src/flynt/utils/utils.py
//! - `fstr_lint`    <- src/flynt/linting/fstr_lint.py
//! - `candidates`   <- src/flynt/candidates/ast_percent_candidates.py + ast_call_candidates.py
//! - `transform`    <- src/flynt/transform/*
//! - `concat`       <- src/flynt/string_concat/*
//! - `static_join`  <- src/flynt/static_join/*
//! - `code_editor`  <- src/flynt/code_editor.py
//! - `api`          <- src/flynt/api.py
//! - `pyproject`    <- src/flynt/utils/pyproject_finder.py
//! - `cli`          <- src/flynt/cli.py

pub mod api;
pub mod astutils;
pub mod candidates;
pub mod chunk;
pub mod cli;
pub mod code_editor;
pub mod concat;
pub mod error;
pub mod fstr_lint;
pub mod pyproject;
pub mod quotes;
pub mod state;
pub mod static_join;
pub mod transform;

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
