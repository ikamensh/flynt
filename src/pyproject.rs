//! Port of src/flynt/utils/pyproject_finder.py. Owner: task #9.

use std::collections::HashMap;
use std::path::{Component, Path, PathBuf};

/// Lexically make a path absolute and normalize `.`/`..` without touching the
/// filesystem (Python's `Path.resolve()` for the non-symlink case, which is all
/// the config lookup relies on — src files may not even exist yet).
fn absolutize(p: &Path) -> PathBuf {
    let joined = if p.is_absolute() {
        p.to_path_buf()
    } else {
        std::env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("/"))
            .join(p)
    };
    normalize(&joined)
}

fn normalize(p: &Path) -> PathBuf {
    let mut out: Vec<Component> = Vec::new();
    for comp in p.components() {
        match comp {
            Component::CurDir => {}
            Component::ParentDir => match out.last() {
                Some(Component::Normal(_)) => {
                    out.pop();
                }
                Some(Component::RootDir) | Some(Component::Prefix(_)) => {}
                _ => out.push(comp),
            },
            c => out.push(c),
        }
    }
    if out.is_empty() {
        PathBuf::from(".")
    } else {
        out.iter().collect()
    }
}

/// Port of `find_project_root`: return a directory containing `.git`, `.hg`, or
/// `pyproject.toml` that is a common parent of all `srcs`. Falls back to the
/// filesystem root when no marker is found.
pub fn find_project_root(srcs: &[String]) -> PathBuf {
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("/"));
    let owned_cwd;
    let srcs: &[String] = if srcs.is_empty() {
        owned_cwd = vec![cwd.to_string_lossy().into_owned()];
        &owned_cwd
    } else {
        srcs
    };

    let path_srcs: Vec<PathBuf> = srcs.iter().map(|s| absolutize(Path::new(s))).collect();

    // For each src: the set of its parents (plus itself if it is a directory).
    let src_parent_sets: Vec<std::collections::HashSet<PathBuf>> = path_srcs
        .iter()
        .map(|p| {
            let mut set: std::collections::HashSet<PathBuf> =
                p.ancestors().skip(1).map(|a| a.to_path_buf()).collect();
            if p.is_dir() {
                set.insert(p.clone());
            }
            set
        })
        .collect();

    let mut common = src_parent_sets[0].clone();
    for s in &src_parent_sets[1..] {
        common = common.intersection(s).cloned().collect();
    }

    // Common base = the deepest (most path components) shared ancestor.
    let common_base = common
        .iter()
        .max_by_key(|p| p.components().count())
        .cloned()
        .unwrap_or_else(|| PathBuf::from("/"));

    let chain: Vec<PathBuf> = std::iter::once(common_base.clone())
        .chain(common_base.ancestors().skip(1).map(|a| a.to_path_buf()))
        .collect();

    let mut last = common_base;
    for dir in chain {
        last = dir.clone();
        if dir.join(".git").exists() {
            return dir;
        }
        if dir.join(".hg").is_dir() {
            return dir;
        }
        if dir.join("pyproject.toml").is_file() {
            return dir;
        }
    }
    last
}

/// Find pyproject.toml starting from the common base of the given paths.
/// Falls back to the user-level config (`flynt.toml`) when no project config
/// exists.
pub fn find_pyproject_toml(paths: &[String]) -> Option<PathBuf> {
    let root = find_project_root(paths);
    let pyproject = root.join("pyproject.toml");
    if pyproject.is_file() {
        return Some(pyproject);
    }

    let user = find_user_config_toml();
    if user.is_file() {
        Some(user)
    } else {
        None
    }
}

/// Port of `find_user_config_toml`: `~\.flynt.toml` on Windows,
/// `$XDG_CONFIG_HOME/flynt.toml` (default `~/.config`) elsewhere.
fn find_user_config_toml() -> PathBuf {
    #[cfg(windows)]
    let path = home_dir().join(".flynt.toml");
    #[cfg(not(windows))]
    let path = {
        let config_root =
            std::env::var("XDG_CONFIG_HOME").unwrap_or_else(|_| "~/.config".to_string());
        expanduser(&config_root).join("flynt.toml")
    };
    absolutize(&path)
}

#[cfg(not(windows))]
fn expanduser(s: &str) -> PathBuf {
    if let Some(rest) = s.strip_prefix('~') {
        let rest = rest.strip_prefix('/').unwrap_or(rest);
        home_dir().join(rest)
    } else {
        PathBuf::from(s)
    }
}

fn home_dir() -> PathBuf {
    #[cfg(windows)]
    let key = "USERPROFILE";
    #[cfg(not(windows))]
    let key = "HOME";
    std::env::var(key)
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("/"))
}

/// Parse a pyproject/flynt toml, pulling out the `[tool.flynt]` section (or the
/// whole file for `flynt.toml`) and normalizing option keys
/// (`--line-length` / `line-length` -> `line_length`).
pub fn parse_pyproject_toml(path: &Path) -> HashMap<String, toml::Value> {
    let text = std::fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("cannot read {}: {e}", path.display()));
    let doc: toml::Value = text
        .parse()
        .unwrap_or_else(|e| panic!("cannot parse {}: {e}", path.display()));

    let mut config: toml::value::Table = doc
        .get("tool")
        .and_then(|t| t.get("flynt"))
        .and_then(|f| f.as_table())
        .cloned()
        .unwrap_or_default();

    if path.to_string_lossy().ends_with("flynt.toml") {
        if let Some(tbl) = doc.as_table() {
            for (k, v) in tbl {
                config.insert(k.clone(), v.clone());
            }
        }
    }

    config
        .into_iter()
        .map(|(k, v)| (k.replace("--", "").replace('-', "_"), v))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    /// Unique temp directory rooted at the OS temp dir (canonicalized so we
    /// don't trip over macOS's /var -> /private/var symlink when checking for
    /// filesystem markers).
    fn temp_dir(tag: &str) -> PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let base = std::env::temp_dir()
            .canonicalize()
            .unwrap_or_else(|_| std::env::temp_dir());
        let dir = base.join(format!("flynt_pyproj_{tag}_{nanos}"));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    const PYPROJECT: &str = "\n[tool.flynt]\nverbose = true\nline_length = 120\n";
    const OTHER_TOOL: &str = "\n[tool.mypy]\nverbose = true\n";

    // Port of test/test_pyproject.py::test_finds_config
    #[test]
    fn finds_config() {
        let root = temp_dir("finds");
        fs::write(root.join("pyproject.toml"), PYPROJECT).unwrap();
        let src = root.join("src");
        fs::create_dir_all(&src).unwrap();
        let pyfile = src.join("foo.py"); // never actually created, matching Python

        let cfg_file =
            find_pyproject_toml(&[pyfile.to_string_lossy().into_owned()]).expect("config found");
        let d = parse_pyproject_toml(&cfg_file);
        assert_eq!(d.get("verbose"), Some(&toml::Value::Boolean(true)));
        assert_eq!(d.get("line_length"), Some(&toml::Value::Integer(120)));
    }

    // Port of test/test_pyproject.py::test_ignores_irrelevant_config
    #[test]
    fn ignores_irrelevant_config() {
        let root = temp_dir("irrelevant");
        fs::write(root.join("pyproject.toml"), OTHER_TOOL).unwrap();
        let src = root.join("src");
        fs::create_dir_all(&src).unwrap();
        let pyfile = src.join("foo.py");

        let cfg_file =
            find_pyproject_toml(&[pyfile.to_string_lossy().into_owned()]).expect("file found");
        let d = parse_pyproject_toml(&cfg_file);
        assert!(d.is_empty());
    }

    // Port of test/test_pyproject.py::test_ignores_subfolder_config
    #[test]
    fn ignores_subfolder_config() {
        // Point the user-config lookup at an empty dir so the fallback finds nothing.
        std::env::set_var("XDG_CONFIG_HOME", temp_dir("xdg_empty"));

        let root = temp_dir("subfolder");
        let other = root.join("other_proj");
        fs::create_dir_all(&other).unwrap();
        fs::write(other.join("pyproject.toml"), PYPROJECT).unwrap();
        let src = root.join("src");
        fs::create_dir_all(&src).unwrap();
        let pyfile = src.join("foo.py");

        let cfg_file = find_pyproject_toml(&[pyfile.to_string_lossy().into_owned()]);
        assert!(cfg_file.is_none(), "subfolder config must not be used");
    }

    #[test]
    fn key_normalization() {
        let root = temp_dir("keynorm");
        fs::write(
            root.join("flynt.toml"),
            "line-length = 100\n\"--verbose\" = true\n",
        )
        .unwrap();
        let d = parse_pyproject_toml(&root.join("flynt.toml"));
        // flynt.toml merges top-level keys and normalizes dashes to underscores.
        assert_eq!(d.get("line_length"), Some(&toml::Value::Integer(100)));
        assert_eq!(d.get("verbose"), Some(&toml::Value::Boolean(true)));
    }
}
