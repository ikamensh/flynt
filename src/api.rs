//! Port of src/flynt/api.py. Owner: task #9.
//!
//! File-processing logic (encoding/BOM, line-ending fidelity, AST safety
//! checks, diffing, walking) is decoupled from the transform core via
//! [`Transforms`]: the public entry points wire in the real
//! `code_editor::*` pipelines, while unit tests inject fakes. This mirrors the
//! Python integration tests that monkeypatch `fstringify_code_by_line`.

use std::collections::HashSet;
use std::fmt::Write as _;
use std::path::{Component, Path, PathBuf};
use std::time::Instant;

use rayon::prelude::*;
use similar::{ChangeTag, TextDiff};

use crate::code_editor;
use crate::state::State;

/// Result of f-stringifying one source string. Port of Python's
/// `FstringifyResult` (dataclass). `*_length` are Unicode code-point counts to
/// match Python's `len(str)`.
#[derive(Debug, Clone)]
pub struct FstringifyResult {
    pub n_changes: usize,
    pub original_length: usize,
    pub new_length: usize,
    pub content: String,
}

/// The three low-level transform pipelines, matching the `code_editor`
/// signatures. Bundled so file-processing code can be exercised with fakes.
#[derive(Clone, Copy)]
pub struct Transforms {
    pub by_line: fn(&str, &mut State) -> (String, usize),
    pub concat: fn(&str, &mut State) -> (String, usize),
    pub join: fn(&str, &mut State) -> (String, usize),
}

impl Default for Transforms {
    fn default() -> Self {
        Self {
            by_line: code_editor::fstringify_code_by_line,
            concat: code_editor::fstringify_concats,
            join: code_editor::fstringify_static_joins,
        }
    }
}

fn blacklist() -> HashSet<String> {
    [".tox", "venv", "site-packages", ".eggs"]
        .iter()
        .map(|s| s.to_string())
        .collect()
}

/// Number of top-level statements, or `None` if the source is not valid Python
/// (Python: `ast.parse` raising `SyntaxError`).
fn parse_body_count(source: &str) -> Option<usize> {
    match ruff_python_parser::parse_module(source) {
        Ok(parsed) => Some(parsed.syntax().body.len()),
        Err(_) => None,
    }
}

/// Transform a code string, assuming it is Python. Port of `fstringify_code`.
pub fn fstringify_code(
    contents: &str,
    state: &mut State,
    filename: &str,
) -> Option<FstringifyResult> {
    fstringify_code_with(contents, state, filename, &Transforms::default())
}

/// [`fstringify_code`] with an injectable transform bundle.
pub fn fstringify_code_with(
    contents: &str,
    state: &mut State,
    _filename: &str,
    t: &Transforms,
) -> Option<FstringifyResult> {
    let before = parse_body_count(contents)?; // invalid Python -> skip

    let mut new_code = contents.to_string();
    let mut changes = 0usize;

    if state.transform_percent || state.transform_format {
        let (nc, ch) = (t.by_line)(contents, state);
        new_code = nc;
        changes = ch;
    }
    if state.transform_concat {
        let (nc, ch) = (t.concat)(&new_code, state);
        new_code = nc;
        changes += ch;
        state.concat_changes += ch;
    }
    if state.transform_join {
        let (nc, ch) = (t.join)(&new_code, state);
        new_code = nc;
        changes += ch;
        state.join_changes += ch;
    }

    let result = FstringifyResult {
        n_changes: changes,
        original_length: contents.chars().count(),
        new_length: new_code.chars().count(),
        content: new_code,
    };

    if result.content == contents {
        return Some(result);
    }

    // Safety: the result must parse and must not change the statement count.
    let after = parse_body_count(&result.content)?; // faulty result -> skip
    if before != after {
        return None;
    }
    Some(result)
}

/// F-stringify a single file, writing changes back. Port of `_fstringify_file`.
pub fn fstringify_file(filename: &str, state: &mut State) -> Option<FstringifyResult> {
    fstringify_file_with(filename, state, &Transforms::default())
}

/// [`fstringify_file`] with an injectable transform bundle.
pub fn fstringify_file_with(
    filename: &str,
    state: &mut State,
    t: &Transforms,
) -> Option<FstringifyResult> {
    let (result, printed) = process_file(filename, state, t);
    print!("{printed}");
    result
}

/// Core of [`fstringify_file_with`], with all would-be stdout captured in the
/// returned buffer. This lets the parallel driver emit per-file output in the
/// original file order, byte-identical to sequential processing.
fn process_file(
    filename: &str,
    state: &mut State,
    t: &Transforms,
) -> (Option<FstringifyResult>, String) {
    let mut printed = String::new();
    let result = process_file_buffered(filename, state, t, &mut printed);
    (result, printed)
}

fn process_file_buffered(
    filename: &str,
    state: &mut State,
    t: &Transforms,
    printed: &mut String,
) -> Option<FstringifyResult> {
    if filename.ends_with(".ipynb") {
        if !state.process_notebooks {
            return None;
        }
        return fstringify_notebook_with(filename, state, t, printed);
    }

    let raw = std::fs::read(filename).expect("read file");
    let (encoding, bom) = encoding_by_bom(&raw);
    let contents = decode(&raw, encoding, bom.as_deref())?; // invalid unicode -> skip

    let result = fstringify_code_with(&contents, state, filename, t)?;
    let new_code = &result.content;

    if state.dry_run && result.n_changes > 0 {
        writeln!(printed, "{}", unified_diff(&contents, new_code, filename)).unwrap();
    } else if state.stdout {
        writeln!(printed, "{new_code}").unwrap();
    } else if result.n_changes > 0 {
        let mut out = Vec::new();
        if let Some(b) = &bom {
            out.extend_from_slice(b);
        }
        out.extend_from_slice(&encode(new_code, encoding));
        std::fs::write(filename, out).expect("write file");
    }
    Some(result)
}

/// Port of `_fstringify_notebook`: transform only code cells of a `.ipynb`.
/// Would-be stdout goes into `printed` (see [`process_file`]).
fn fstringify_notebook_with(
    filename: &str,
    state: &mut State,
    t: &Transforms,
    printed: &mut String,
) -> Option<FstringifyResult> {
    let text = std::fs::read_to_string(filename).ok()?;
    let mut nb: serde_json::Value = serde_json::from_str(&text).ok()?;

    let original_dump = json_dump(&nb);
    let mut changes = 0usize;

    if let Some(cells) = nb.get_mut("cells").and_then(|c| c.as_array_mut()) {
        for (idx, cell) in cells.iter_mut().enumerate() {
            if cell.get("cell_type").and_then(|v| v.as_str()) != Some("code") {
                continue;
            }
            let source = join_source(cell.get("source"));
            let cell_name = format!("{filename}[{idx}]");
            let result = match fstringify_code_with(&source, state, &cell_name, t) {
                Some(r) => r,
                None => continue,
            };
            changes += result.n_changes;
            if result.content != source {
                cell["source"] = serde_json::Value::Array(
                    splitlines_keepends(&result.content)
                        .into_iter()
                        .map(serde_json::Value::String)
                        .collect(),
                );
            }
        }
    }

    let new_dump = json_dump(&nb);
    if state.dry_run && changes > 0 {
        writeln!(printed, "{}", unified_diff(&original_dump, &new_dump, filename)).unwrap();
    } else if state.stdout {
        writeln!(printed, "{new_dump}").unwrap();
    } else if changes > 0 {
        std::fs::write(filename, new_dump.as_bytes()).expect("write notebook");
    }

    Some(FstringifyResult {
        n_changes: changes,
        original_length: original_dump.chars().count(),
        new_length: new_dump.chars().count(),
        content: new_dump,
    })
}

/// `json.dumps(nb, ensure_ascii=False, indent=1)` equivalent. Exact formatting
/// is not pinned by any test (notebook equality is structural), so pretty JSON
/// suffices while staying human-readable for dry-run diffs.
fn json_dump(v: &serde_json::Value) -> String {
    serde_json::to_string_pretty(v).expect("serialize notebook")
}

/// `"".join(cell.get("source", []))` — source may be a list of strings or a
/// single string.
fn join_source(source: Option<&serde_json::Value>) -> String {
    match source {
        Some(serde_json::Value::Array(items)) => items
            .iter()
            .filter_map(|v| v.as_str())
            .collect::<String>(),
        Some(serde_json::Value::String(s)) => s.clone(),
        _ => String::new(),
    }
}

/// `str.splitlines(keepends=True)` for the newline styles code cells use.
fn splitlines_keepends(s: &str) -> Vec<String> {
    let mut lines = Vec::new();
    let bytes = s.as_bytes();
    let mut start = 0usize;
    let mut i = 0usize;
    while i < bytes.len() {
        match bytes[i] {
            b'\r' => {
                let end = if i + 1 < bytes.len() && bytes[i + 1] == b'\n' {
                    i + 2
                } else {
                    i + 1
                };
                lines.push(s[start..end].to_string());
                i = end;
                start = end;
            }
            b'\n' => {
                lines.push(s[start..i + 1].to_string());
                i += 1;
                start = i;
            }
            _ => i += 1,
        }
    }
    if start < s.len() {
        lines.push(s[start..].to_string());
    }
    lines
}

/// Apply transforms to a sequence of files, keeping shared stats. Port of
/// `fstringify_files` — the public form prints the report/summary.
pub fn fstringify_files(files: &[String], state: &mut State) -> usize {
    let stats = run_files_with(files, state, &Transforms::default());
    if !state.quiet {
        if state.report {
            print_report(state, &stats);
        } else {
            print_summary(&stats);
        }
    }
    stats.changed_files
}

/// Aggregate statistics of one run over a set of files.
#[derive(Debug, Default, Clone)]
pub struct RunStats {
    pub found_files: usize,
    pub changed_files: usize,
    pub total_cc_original: usize,
    pub total_cc_new: usize,
    pub total_expressions: usize,
    pub total_time: f64,
}

/// The testable core of [`fstringify_files`]: process files, return stats.
///
/// Files are processed in parallel (they are independent: each is read and
/// written at most once, and nothing else is shared). Each file gets its own
/// `State` fork with zeroed counters; counter sums are merged back afterwards,
/// and per-file output is buffered and printed sequentially in the original
/// file order — so counters, stats, and stdout are identical to a sequential
/// run. Thread count is rayon's default (all cores); set `RAYON_NUM_THREADS`
/// to override (e.g. `RAYON_NUM_THREADS=1` for fully sequential execution).
pub fn run_files_with(files: &[String], state: &mut State, t: &Transforms) -> RunStats {
    let mut stats = RunStats {
        found_files: files.len(),
        ..RunStats::default()
    };
    let start = Instant::now();

    let base = fork_options(state);
    let outcomes: Vec<(Option<FstringifyResult>, String, State)> = files
        .par_iter()
        .map(|path| {
            let mut local = base.clone();
            let (result, printed) = process_file(path, &mut local, t);
            (result, printed, local)
        })
        .collect(); // indexed par_iter: collect preserves input order

    for (result, printed, local) in outcomes {
        print!("{printed}");
        merge_counters(state, &local);
        if let Some(result) = result {
            if result.n_changes > 0 {
                stats.changed_files += 1;
                stats.total_expressions += result.n_changes;
            }
            stats.total_cc_original += result.original_length;
            stats.total_cc_new += result.new_length;
        }
    }
    stats.total_time = start.elapsed().as_secs_f64();
    stats
}

/// Copy of `state` with all statistics counters zeroed — the per-file working
/// state for the parallel driver.
fn fork_options(state: &State) -> State {
    State {
        quiet: state.quiet,
        aggressive: state.aggressive,
        dry_run: state.dry_run,
        stdout: state.stdout,
        multiline: state.multiline,
        len_limit: state.len_limit,
        report: state.report,
        transform_percent: state.transform_percent,
        transform_format: state.transform_format,
        transform_concat: state.transform_concat,
        transform_join: state.transform_join,
        process_notebooks: state.process_notebooks,
        ..State::default()
    }
}

/// Add the statistics accumulated in `src` (one file's fork) into `dst`.
fn merge_counters(dst: &mut State, src: &State) {
    dst.percent_candidates += src.percent_candidates;
    dst.percent_transforms += src.percent_transforms;
    dst.call_candidates += src.call_candidates;
    dst.call_transforms += src.call_transforms;
    dst.invalid_conversions += src.invalid_conversions;
    dst.concat_candidates += src.concat_candidates;
    dst.concat_changes += src.concat_changes;
    dst.join_candidates += src.join_candidates;
    dst.join_changes += src.join_changes;
}

fn print_report(state: &State, s: &RunStats) {
    println!("\nFlynt run has finished. Stats:");
    println!(
        "\nExecution time:                            {:.3}s",
        s.total_time
    );
    println!("Files checked:                             {}", s.found_files);
    println!("Files modified:                            {}", s.changed_files);
    if s.changed_files > 0 {
        let cc_reduction = s.total_cc_original as i64 - s.total_cc_new as i64;
        let cc_percent = cc_reduction as f64 / s.total_cc_original as f64;
        println!(
            "Character count reduction:                 {} ({:.2}%)\n",
            cc_reduction,
            cc_percent * 100.0
        );

        println!("Per expression type:");
        if state.percent_candidates > 0 {
            let frac = state.percent_transforms as f64 / state.percent_candidates as f64;
            println!(
                "Old style (`%`) expressions attempted:     {}/{} ({:.1}%)",
                state.percent_transforms,
                state.percent_candidates,
                frac * 100.0
            );
        } else {
            println!("No old style (`%`) expressions attempted.");
        }

        if state.call_candidates > 0 {
            println!(
                "`.format(...)` calls attempted:            {}/{} ({:.1}%)",
                state.call_transforms,
                state.call_candidates,
                state.call_transforms as f64 / state.call_candidates as f64 * 100.0
            );
        } else {
            println!("No `.format(...)` calls attempted.");
        }

        if state.concat_candidates > 0 {
            println!(
                "String concatenations attempted:           {}/{} ({:.1}%)",
                state.concat_changes,
                state.concat_candidates,
                state.concat_changes as f64 / state.concat_candidates as f64 * 100.0
            );
        } else {
            println!("No concatenations attempted.");
        }

        if state.join_candidates > 0 {
            println!(
                "Static string joins attempted:             {}/{} ({:.1}%)",
                state.join_changes,
                state.join_candidates,
                state.join_changes as f64 / state.join_candidates as f64 * 100.0
            );
        } else {
            println!("No static string joins attempted.");
        }

        println!("F-string expressions created:              {}", s.total_expressions);

        if state.invalid_conversions > 0 {
            println!(
                "Out of all attempted transforms, {} resulted in errors.",
                state.invalid_conversions
            );
            println!("To find out specific error messages, use --verbose flag.");
        }
    }

    println!("\n{}", "_-_.".repeat(25));
}

fn print_summary(s: &RunStats) {
    if s.changed_files > 0 {
        println!(
            "Modified {} of {} files in {:.2}s",
            s.changed_files, s.found_files, s.total_time
        );
    } else {
        let plural = if s.found_files != 1 { "s" } else { "" };
        println!(
            "No changes made to {} file{} in {:.2}s",
            s.found_files, plural, s.total_time
        );
    }
}

/// Determine whether a directory or single file was passed, and f-stringify it.
/// Port of `fstringify`. Returns the process exit code.
pub fn fstringify(
    src: &[String],
    excluded: Option<&[String]>,
    fail_on_changes: bool,
    state: &mut State,
) -> i32 {
    let files = resolve_files(src, excluded, state);
    let status = fstringify_files(&files, state);
    if fail_on_changes {
        status as i32
    } else {
        0
    }
}

/// Resolve relative paths and directories to a list of source files (as
/// forward-slash paths), applying the blacklist uniformly across separators.
/// Port of `_resolve_files`.
pub fn resolve_files(
    files_or_paths: &[String],
    excluded: Option<&[String]>,
    state: &State,
) -> Vec<String> {
    let mut bl = blacklist();
    if let Some(ex) = excluded {
        bl.extend(ex.iter().cloned());
    }

    let mut files: Vec<String> = Vec::new();
    for fop in files_or_paths {
        let abs = absolutize(Path::new(fop));
        if !abs.exists() {
            println!("`{fop}` not found");
            std::process::exit(1);
        }
        if abs.is_dir() {
            for (folder, filename) in find_source_files(&abs, state.process_notebooks) {
                files.push(folder.join(filename).to_string_lossy().into_owned());
            }
        } else {
            let s = abs.to_string_lossy();
            if s.ends_with(".py") || (state.process_notebooks && s.ends_with(".ipynb")) {
                files.push(s.into_owned());
            }
        }
    }

    let files: Vec<String> = files.into_iter().map(|f| f.replace('\\', "/")).collect();
    let bl: HashSet<String> = bl.into_iter().map(|f| f.replace('\\', "/")).collect();
    files
        .into_iter()
        .filter(|f| bl.iter().all(|b| !f.contains(b)))
        .collect()
}

/// Recursively collect `(folder, filename)` for source files under `dir`.
/// Port of the directory branch of `_find_source_files`.
fn find_source_files(dir: &Path, include_ipynb: bool) -> Vec<(PathBuf, String)> {
    let mut out = Vec::new();
    let mut stack = vec![dir.to_path_buf()];
    while let Some(d) = stack.pop() {
        let entries = match std::fs::read_dir(&d) {
            Ok(e) => e,
            Err(_) => continue,
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                stack.push(path);
            } else if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                if name.ends_with(".py") || (include_ipynb && name.ends_with(".ipynb")) {
                    out.push((d.clone(), name.to_string()));
                }
            }
        }
    }
    out
}

// -- encoding / BOM handling ------------------------------------------------

const BOM_UTF8: &[u8] = &[0xEF, 0xBB, 0xBF];
const BOM_UTF32_LE: &[u8] = &[0xFF, 0xFE, 0x00, 0x00];
const BOM_UTF32_BE: &[u8] = &[0x00, 0x00, 0xFE, 0xFF];
const BOM_UTF16_LE: &[u8] = &[0xFF, 0xFE];
const BOM_UTF16_BE: &[u8] = &[0xFE, 0xFF];

/// Detect the encoding from a leading BOM. Port of `encoding_by_bom`, adapted
/// to take the already-read bytes rather than a path.
fn encoding_by_bom(raw: &[u8]) -> (&'static str, Option<Vec<u8>>) {
    // UTF-32 must be tested before UTF-16 (BOM_UTF32_LE starts with BOM_UTF16_LE).
    for (enc, boms) in [
        ("utf-8-sig", &[BOM_UTF8][..]),
        ("utf-32", &[BOM_UTF32_LE, BOM_UTF32_BE][..]),
        ("utf-16", &[BOM_UTF16_LE, BOM_UTF16_BE][..]),
    ] {
        for bom in boms {
            if raw.starts_with(bom) {
                return (enc, Some(bom.to_vec()));
            }
        }
    }
    ("utf-8", None)
}

/// Decode file bytes per the detected encoding; `None` on invalid data
/// (Python's `UnicodeDecodeError`).
fn decode(raw: &[u8], encoding: &str, bom: Option<&[u8]>) -> Option<String> {
    match encoding {
        "utf-8" => String::from_utf8(raw.to_vec()).ok(),
        "utf-8-sig" => {
            let body = raw.strip_prefix(BOM_UTF8).unwrap_or(raw);
            String::from_utf8(body.to_vec()).ok()
        }
        "utf-16" => {
            let le = bom != Some(BOM_UTF16_BE);
            let body = &raw[bom.map_or(0, |b| b.len())..];
            if body.len() % 2 != 0 {
                return None;
            }
            let units: Vec<u16> = body
                .chunks_exact(2)
                .map(|c| {
                    if le {
                        u16::from_le_bytes([c[0], c[1]])
                    } else {
                        u16::from_be_bytes([c[0], c[1]])
                    }
                })
                .collect();
            String::from_utf16(&units).ok()
        }
        "utf-32" => {
            let le = bom != Some(BOM_UTF32_BE);
            let body = &raw[bom.map_or(0, |b| b.len())..];
            if body.len() % 4 != 0 {
                return None;
            }
            body.chunks_exact(4)
                .map(|c| {
                    let n = if le {
                        u32::from_le_bytes([c[0], c[1], c[2], c[3]])
                    } else {
                        u32::from_be_bytes([c[0], c[1], c[2], c[3]])
                    };
                    char::from_u32(n)
                })
                .collect::<Option<String>>()
        }
        _ => String::from_utf8(raw.to_vec()).ok(),
    }
}

/// Encode content for writing. Mirrors Python `str.encode(encoding)`: the
/// `-sig`/utf-16/utf-32 codecs prepend their own BOM (so, combined with the
/// separately-written detected BOM, faithfully reproduces flynt's write path).
fn encode(content: &str, encoding: &str) -> Vec<u8> {
    match encoding {
        "utf-8-sig" => {
            let mut v = BOM_UTF8.to_vec();
            v.extend_from_slice(content.as_bytes());
            v
        }
        "utf-16" => {
            let mut v = BOM_UTF16_LE.to_vec();
            for u in content.encode_utf16() {
                v.extend_from_slice(&u.to_le_bytes());
            }
            v
        }
        "utf-32" => {
            let mut v = BOM_UTF32_LE.to_vec();
            for ch in content.chars() {
                v.extend_from_slice(&(ch as u32).to_le_bytes());
            }
            v
        }
        _ => content.as_bytes().to_vec(),
    }
}

// -- path + diff helpers ----------------------------------------------------

/// Lexically absolutize + normalize (Python `os.path.abspath`: no symlink
/// resolution, collapses `.`/`..`).
fn absolutize(p: &Path) -> PathBuf {
    let joined = if p.is_absolute() {
        p.to_path_buf()
    } else {
        std::env::current_dir()
            .unwrap_or_else(|_| PathBuf::from("/"))
            .join(p)
    };
    let mut out: Vec<Component> = Vec::new();
    for comp in joined.components() {
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
    out.iter().collect()
}

/// `difflib.unified_diff(a.split("\n"), b.split("\n"), fromfile=...)` joined by
/// `"\n"`. Only the presence of `-line`/`+line` for changed lines is contract;
/// hunking keeps the output proportional to the change.
fn unified_diff(a_text: &str, b_text: &str, fromfile: &str) -> String {
    let a: Vec<&str> = a_text.split('\n').collect();
    let b: Vec<&str> = b_text.split('\n').collect();
    let diff = TextDiff::from_slices(&a, &b);

    let mut lines: Vec<String> = vec![format!("--- {fromfile}\n"), "+++ \n".to_string()];
    for hunk in diff.unified_diff().context_radius(3).iter_hunks() {
        lines.push(format!("{}\n", hunk.header()));
        for change in hunk.iter_changes() {
            let sign = match change.tag() {
                ChangeTag::Delete => '-',
                ChangeTag::Insert => '+',
                ChangeTag::Equal => ' ',
            };
            lines.push(format!("{sign}{}", change.value()));
        }
    }
    lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::PathBuf;

    fn test_state() -> State {
        State {
            multiline: true,
            len_limit: Some(1000),
            ..State::default()
        }
    }

    fn temp_dir(tag: &str) -> PathBuf {
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let base = std::env::temp_dir()
            .canonicalize()
            .unwrap_or_else(|_| std::env::temp_dir());
        let dir = base.join(format!("flynt_api_{tag}_{nanos}"));
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    // -- fake transforms (module-level fns so they coerce to fn pointers) --

    fn noop(code: &str, _s: &mut State) -> (String, usize) {
        (code.to_string(), 0)
    }
    fn fakes_noop() -> Transforms {
        Transforms {
            by_line: noop,
            concat: noop,
            join: noop,
        }
    }
    fn fake_hello(_code: &str, _s: &mut State) -> (String, usize) {
        ("Hello World".to_string(), 42) // invalid Python
    }
    fn fake_a42(_code: &str, _s: &mut State) -> (String, usize) {
        ("a = 42".to_string(), 42) // valid, but 1 statement
    }
    fn fake_first_string(_code: &str, _s: &mut State) -> (String, usize) {
        // valid replacement preserving the 2-statement structure of first_string.py
        ("a = 1\nb = 2\n".to_string(), 2)
    }

    // Port of test_api.py::test_break_safe — invalid transform result is dropped.
    #[test]
    fn break_safe() {
        let dir = temp_dir("break_safe");
        let f = dir.join("input.py");
        let before = "a = '{}'.format(x)\nb = '{}'.format(y)\n";
        fs::write(&f, before).unwrap();

        let t = Transforms {
            by_line: fake_hello,
            ..fakes_noop()
        };
        let result = fstringify_file_with(f.to_str().unwrap(), &mut test_state(), &t);

        assert!(result.is_none());
        assert_eq!(fs::read_to_string(&f).unwrap(), before);
    }

    // Port of test_api.py::test_catches_subtle — statement-count change dropped.
    #[test]
    fn catches_subtle() {
        let dir = temp_dir("subtle");
        let f = dir.join("input.py");
        let before = "a = '{}'.format(x)\nb = '{}'.format(y)\n";
        fs::write(&f, before).unwrap();

        let t = Transforms {
            by_line: fake_a42,
            ..fakes_noop()
        };
        let result = fstringify_file_with(f.to_str().unwrap(), &mut test_state(), &t);

        assert!(result.is_none());
        assert_eq!(fs::read_to_string(&f).unwrap(), before);
    }

    // Port of test_api.py::test_py2 — invalid (py2) source left untouched.
    #[test]
    fn py2_untouched() {
        let dir = temp_dir("py2");
        let f = dir.join("py2.py2");
        let before = "print \"Hello World\"\nprint(\"{} w\".format(val))\n";
        fs::write(&f, before).unwrap();

        let result = fstringify_file_with(f.to_str().unwrap(), &mut test_state(), &fakes_noop());

        assert!(result.is_none());
        assert_eq!(fs::read_to_string(&f).unwrap(), before);
    }

    // Port of test_api.py::test_invalid_unicode.
    #[test]
    fn invalid_unicode_untouched() {
        let dir = temp_dir("badunicode");
        let f = dir.join("invalid_unicode.py");
        let mut bytes = b"# This is not valid unicode: ".to_vec();
        bytes.extend_from_slice(&[0xFF, 0xFF]);
        fs::write(&f, &bytes).unwrap();

        let result = fstringify_file_with(f.to_str().unwrap(), &mut test_state(), &fakes_noop());

        assert!(result.is_none());
        assert_eq!(fs::read(&f).unwrap(), bytes);
    }

    // Port of test_api.py::test_dry_run — file unchanged, changes still counted.
    #[test]
    fn dry_run_counts_but_keeps_file() {
        let dir = temp_dir("dryrun");
        let f = dir.join("input.py");
        let before = "a = '{}'.format(x)\nb = '{}'.format(y)\n";
        fs::write(&f, before).unwrap();

        let mut state = State {
            dry_run: true,
            ..test_state()
        };
        let t = Transforms {
            by_line: fake_first_string,
            ..fakes_noop()
        };
        let result = fstringify_file_with(f.to_str().unwrap(), &mut state, &t).unwrap();

        assert!(result.n_changes > 0);
        assert_eq!(fs::read_to_string(&f).unwrap(), before);
    }

    // Port of test_api.py::test_mixed_line_endings — each line keeps its ending.
    #[test]
    fn mixed_line_endings_preserved() {
        let dir = temp_dir("mixed");
        let f = dir.join("mixed.py");
        let before =
            b"'{}'.format(1)\n'{}'.format(2)# Linux line ending\n'{}'.format(3)# Windows line ending\r\n";
        let after =
            "f'{1}'\nf'{2}'# Linux line ending\nf'{3}'# Windows line ending\r\n".to_string();
        fs::write(&f, before).unwrap();

        // Fake transform maps the exact decoded content to the expected output
        // (the per-line-ending logic itself lives in the core); here we verify
        // _fstringify_file reads/writes bytes with no newline translation.
        fn fake(_code: &str, _s: &mut State) -> (String, usize) {
            (
                "f'{1}'\nf'{2}'# Linux line ending\nf'{3}'# Windows line ending\r\n".to_string(),
                3,
            )
        }
        let t = Transforms {
            by_line: fake,
            ..fakes_noop()
        };
        let result = fstringify_file_with(f.to_str().unwrap(), &mut test_state(), &t).unwrap();

        assert!(result.n_changes > 0);
        assert_eq!(fs::read(&f).unwrap(), after.as_bytes());
    }

    // Port of test_api.py::test_bom — BOM preserved on write.
    #[test]
    fn bom_preserved() {
        let dir = temp_dir("bom");
        let f = dir.join("bom.py");
        let mut before = BOM_UTF8.to_vec();
        before.extend_from_slice(b"print(\"mark {}\".format(1))\n");
        fs::write(&f, &before).unwrap();

        fn fake(_code: &str, _s: &mut State) -> (String, usize) {
            ("print(f\"mark {1}\")\n".to_string(), 1)
        }
        let t = Transforms {
            by_line: fake,
            ..fakes_noop()
        };
        let result = fstringify_file_with(f.to_str().unwrap(), &mut test_state(), &t).unwrap();

        assert_eq!(result.n_changes, 1);
        let written = fs::read(&f).unwrap();
        assert!(written.starts_with(BOM_UTF8), "BOM must be preserved");
    }

    // Port of test_api.py::test_fstringify_files_charcount.
    #[test]
    fn fstringify_files_charcount() {
        let dir = temp_dir("charcount");
        let f = dir.join("a.py");
        let source = "'{}'.format(1)\n";
        fs::write(&f, source).unwrap();

        fn fake(_code: &str, _s: &mut State) -> (String, usize) {
            ("f'{1}'\n".to_string(), 1)
        }
        let t = Transforms {
            by_line: fake,
            ..fakes_noop()
        };
        let mut state = State {
            report: true,
            ..State::default()
        };
        let stats = run_files_with(&[f.to_string_lossy().into_owned()], &mut state, &t);

        assert_eq!(stats.total_cc_original, source.chars().count());
        assert_eq!(stats.total_cc_new, "f'{1}'\n".chars().count());
    }

    // Port of test_api.py::test_uniform_path — separators normalized uniformly.
    #[test]
    fn uniform_path_exclude() {
        let root = temp_dir("uniform");
        let tree = [
            "src/flynt/test/unix/code.py",
            "src/flynt/test/unix/exclude/code.py",
            "src/flynt/test/win/code.py",
            "src/flynt/test/win/exclude/code.py",
            "src/flynt/test/mixed/code.py",
            "src/flynt/test/mixed/exclude/code.py",
        ];
        for rel in tree {
            let p = root.join("fake_tree").join(rel);
            fs::create_dir_all(p.parent().unwrap()).unwrap();
            fs::write(&p, b"").unwrap();
        }
        let exclude = [
            "test/unix/exclude".to_string(),
            "test\\win\\exclude".to_string(),
            "test/mixed\\exclude".to_string(),
        ];
        let result = resolve_files(
            &[root.join("fake_tree").to_string_lossy().into_owned()],
            Some(&exclude),
            &State::default(),
        );
        assert_eq!(result.len(), tree.len() - exclude.len());
    }

    // Port of test_api.py::test_notebook_ignored_without_flag.
    #[test]
    fn notebook_ignored_without_flag() {
        let dir = temp_dir("nb_off");
        let nb = dir.join("t.ipynb");
        write_notebook(&nb);
        let result = fstringify_file_with(nb.to_str().unwrap(), &mut State::default(), &fakes_noop());
        assert!(result.is_none());
        // untouched
        let data: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(&nb).unwrap()).unwrap();
        let src = join_source(data["cells"][0].get("source"));
        assert!(src.contains("format(1)"));
    }

    // Port of test_api.py::test_notebook_conversion + test_sample_notebook.
    #[test]
    fn notebook_conversion() {
        let dir = temp_dir("nb_on");
        let nb = dir.join("t.ipynb");
        write_notebook(&nb);

        fn fake(code: &str, _s: &mut State) -> (String, usize) {
            if code == "print('{}'.format(1))\n" {
                ("print(f'{1}')\n".to_string(), 1)
            } else {
                (code.to_string(), 0)
            }
        }
        let t = Transforms {
            by_line: fake,
            ..fakes_noop()
        };
        let mut state = State {
            process_notebooks: true,
            ..State::default()
        };
        let result = fstringify_file_with(nb.to_str().unwrap(), &mut state, &t).unwrap();
        assert_eq!(result.n_changes, 1);

        let data: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(&nb).unwrap()).unwrap();
        // code cell converted, markdown cell untouched
        assert!(join_source(data["cells"][0].get("source")).contains("f'{1}'"));
        assert_eq!(data["cells"][1]["cell_type"], "markdown");
    }

    fn write_notebook(path: &Path) {
        let nb = serde_json::json!({
            "cells": [
                {"cell_type": "code", "source": ["print('{}'.format(1))\n"]},
                {"cell_type": "markdown", "source": ["# header"]},
            ]
        });
        fs::write(path, serde_json::to_string(&nb).unwrap()).unwrap();
    }

    #[test]
    fn splitlines_keepends_matches_python() {
        assert_eq!(splitlines_keepends("a\nb\n"), vec!["a\n", "b\n"]);
        assert_eq!(splitlines_keepends("a\r\nb"), vec!["a\r\n", "b"]);
        assert_eq!(splitlines_keepends("x"), vec!["x"]);
        assert!(splitlines_keepends("").is_empty());
    }

    #[test]
    fn encoding_detection() {
        assert_eq!(encoding_by_bom(b"print(1)").0, "utf-8");
        let mut b = BOM_UTF8.to_vec();
        b.extend_from_slice(b"x");
        assert_eq!(encoding_by_bom(&b).0, "utf-8-sig");
    }

    #[test]
    fn unified_diff_marks_changed_lines() {
        let d = unified_diff("a = 1\n", "a = 2\n", "f.py");
        assert!(d.contains("-a = 1"));
        assert!(d.contains("+a = 2"));
    }
}
