//! Port of src/flynt/state.py — options + conversion statistics.

/// A user-facing note about a candidate that was not converted, emitted at
/// `-v` as `file:line: message`. The line is 1-based and refers to the text
/// the recording pipeline ran on.
#[derive(Debug, Clone)]
pub struct Diagnostic {
    pub line: usize,
    pub message: String,
}

#[derive(Debug, Clone)]
pub struct State {
    // -- Options
    pub quiet: bool,
    /// Verbosity: 0 = summary only, 1 = modified files + refusal
    /// diagnostics, 2 = also files scanned without changes.
    pub verbose: u32,
    pub aggressive: u8,
    pub dry_run: bool,
    pub stdout: bool,
    pub multiline: bool,
    /// `None` means no limit (Python: len_limit=None -> sys.maxsize in CodeEditor).
    pub len_limit: Option<usize>,
    pub report: bool,
    pub transform_percent: bool,
    pub transform_format: bool,
    pub transform_concat: bool,
    pub transform_join: bool,
    pub process_notebooks: bool,

    // -- Statistics
    pub percent_candidates: usize,
    pub percent_transforms: usize,
    pub call_candidates: usize,
    pub call_transforms: usize,
    pub invalid_conversions: usize,
    pub concat_candidates: usize,
    pub concat_changes: usize,
    pub join_candidates: usize,
    pub join_changes: usize,

    // -- Diagnostics (per-file; drained by the file driver when it flushes
    // the file's buffered output)
    /// Located notes, ready to print.
    pub diagnostics: Vec<Diagnostic>,
    /// Reasons recorded inside a transform, where the source position isn't
    /// known; CodeEditor attaches the current chunk's line right after the
    /// transform call.
    pub pending_reasons: Vec<String>,
}

impl Default for State {
    fn default() -> Self {
        Self {
            quiet: false,
            verbose: 0,
            aggressive: 0,
            dry_run: false,
            stdout: false,
            multiline: true,
            len_limit: None,
            report: false,
            transform_percent: true,
            transform_format: true,
            transform_concat: false,
            transform_join: false,
            process_notebooks: false,
            percent_candidates: 0,
            percent_transforms: 0,
            call_candidates: 0,
            call_transforms: 0,
            invalid_conversions: 0,
            concat_candidates: 0,
            concat_changes: 0,
            join_candidates: 0,
            join_changes: 0,
            diagnostics: Vec::new(),
            pending_reasons: Vec::new(),
        }
    }
}

impl State {
    /// Python `State.__post_init__`: `if not multiline: len_limit = 0`.
    /// Call after constructing with non-default `multiline`.
    pub fn finalize(mut self) -> Self {
        if !self.multiline {
            self.len_limit = Some(0);
        }
        self
    }

    /// Record a refusal reason from inside a transform (no position known yet).
    pub fn pend_reason(&mut self, message: impl Into<String>) {
        if self.verbose > 0 {
            self.pending_reasons.push(message.into());
        }
    }

    /// Record a located diagnostic (`line` is 1-based).
    pub fn diag(&mut self, line: usize, message: impl Into<String>) {
        if self.verbose > 0 {
            self.diagnostics.push(Diagnostic {
                line,
                message: message.into(),
            });
        }
    }
}
