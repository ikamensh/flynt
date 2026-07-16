//! Port of src/flynt/utils/pyproject_finder.py. Owner: task #9.

use std::collections::HashMap;
use std::path::{Path, PathBuf};

/// Find pyproject.toml starting from the common base of the given paths.
pub fn find_pyproject_toml(paths: &[String]) -> Option<PathBuf> {
    let _ = paths;
    todo!("task #9")
}

/// Parse [tool.flynt] section into option key -> TOML value.
pub fn parse_pyproject_toml(path: &Path) -> HashMap<String, toml::Value> {
    let _ = path;
    todo!("task #9")
}
