//! Port of src/flynt/state.py — options + conversion statistics.

#[derive(Debug, Clone)]
pub struct State {
    // -- Options
    pub quiet: bool,
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
}

impl Default for State {
    fn default() -> Self {
        Self {
            quiet: false,
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
}
