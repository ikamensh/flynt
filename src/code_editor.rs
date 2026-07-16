//! Port of src/flynt/code_editor.py. Owner: task #7.
//!
//! CodeEditor applies local edits while keeping the rest of the original
//! source byte-for-byte. See the Python docstring for the invariants;
//! candidates arrive ordered first-to-last.
//!
//! Byte-vs-char decision: Python splits the source with `code.split("\n")` and
//! works line-by-line. AST column offsets are utf-8 *byte* offsets, converted to
//! *char* indices per line via `_byte_to_char_idx`; every subsequent slice,
//! `len`, and length-limit comparison is then char-based. We keep the same shape:
//! `Chunk.range` is a whole-source byte range, which we map to `(line, byte_col)`
//! and then to char indices exactly like `_byte_to_char_idx`, so observable
//! output is identical on multi-byte unicode files.

use std::collections::HashMap;

use ruff_python_ast::Expr;

use crate::astutils::{apply_unicode_escape_map, contains_comment, unicode_escape_map};
use crate::chunk::Chunk;
use crate::quotes::{get_quote_type, get_string_prefix, QuoteType};
use crate::state::State;
use crate::{candidates, concat, static_join, transform};

/// The transform callback shape shared by all three pipelines:
/// (node, state, quote_type) -> (converted_source, changed).
pub type TransformFunc = fn(&Expr, &mut State, QuoteType) -> (String, bool);

/// Candidate discovery callback: code + state -> ordered chunks.
pub type CandidatesFunc = fn(&str, &mut State) -> Vec<Chunk>;

/// Port of fstringify_code_by_line: returns (new_code, count_of_edits).
pub fn fstringify_code_by_line(code: &str, state: &mut State) -> (String, usize) {
    let len_limit = state.len_limit;
    transform_code(
        code,
        len_limit,
        candidates::fstring_candidates,
        transform::transform_chunk,
        state,
    )
}

/// Port of fstringify_concats.
pub fn fstringify_concats(code: &str, state: &mut State) -> (String, usize) {
    let len_limit = state.len_limit;
    transform_code(
        code,
        len_limit,
        concat::concat_candidates,
        concat::transform_concat,
        state,
    )
}

/// Port of fstringify_static_joins.
pub fn fstringify_static_joins(code: &str, state: &mut State) -> (String, usize) {
    let len_limit = state.len_limit;
    transform_code(
        code,
        len_limit,
        static_join::join_candidates,
        static_join::transform_join,
        state,
    )
}

/// Port of `_transform_code`: discover candidates, then run the edit loop.
fn transform_code<C, F>(
    code: &str,
    len_limit: Option<usize>,
    candidates_factory: C,
    transform_func: F,
    state: &mut State,
) -> (String, usize)
where
    C: FnOnce(&str, &mut State) -> Vec<Chunk>,
    F: FnMut(&Expr, &mut State, QuoteType) -> (String, bool),
{
    let chunks = candidates_factory(code, state);
    EditEngine::new(code, len_limit).edit(chunks, state, transform_func)
}

// --- char-index helpers (Python str slicing is by char, not byte) ------------

fn clen(s: &str) -> usize {
    s.chars().count()
}

/// Chars `[start, end)` of `s` (Python `s[start:end]`, out-of-range clamped).
fn cslice(s: &str, start: usize, end: usize) -> String {
    s.chars().skip(start).take(end.saturating_sub(start)).collect()
}

/// Chars from `start` onward (Python `s[start:]`).
fn cslice_from(s: &str, start: usize) -> String {
    s.chars().skip(start).collect()
}

/// Char at index `idx`, if any (Python `s[idx]`).
fn char_at(s: &str, idx: usize) -> Option<char> {
    s.chars().nth(idx)
}

/// Python `string.whitespace` is an ASCII-only set, unlike `char::is_whitespace`.
fn is_py_whitespace(c: char) -> bool {
    matches!(c, ' ' | '\t' | '\n' | '\r' | '\u{0b}' | '\u{0c}')
}

/// True if `chars[pos..]` starts with `pat`.
fn starts_with_at(chars: &[char], pos: usize, pat: &str) -> bool {
    let p: Vec<char> = pat.chars().collect();
    if pos + p.len() > chars.len() {
        return false;
    }
    chars[pos..pos + p.len()] == p[..]
}

/// True if `pat` occurs anywhere at or after `from`.
fn contains_from(chars: &[char], from: usize, pat: &str) -> bool {
    let p: Vec<char> = pat.chars().collect();
    if p.is_empty() {
        return true;
    }
    if chars.len() < p.len() {
        return false;
    }
    (from..=chars.len() - p.len()).any(|k| chars[k..k + p.len()] == p[..])
}

/// Port of `noqa_regex = re.compile("#[ ]*noqa.*flynt")`, searched anywhere.
fn noqa_match(line: &str) -> bool {
    let chars: Vec<char> = line.chars().collect();
    for i in 0..chars.len() {
        if chars[i] != '#' {
            continue;
        }
        let mut j = i + 1;
        while j < chars.len() && chars[j] == ' ' {
            j += 1;
        }
        if starts_with_at(&chars, j, "noqa") && contains_from(&chars, j + 4, "flynt") {
            return true;
        }
    }
    false
}

/// Port of `flynt_skip_regex = re.compile(r"#\s*flynt:\s*skip")`, searched anywhere.
fn flynt_skip_match(line: &str) -> bool {
    let chars: Vec<char> = line.chars().collect();
    for i in 0..chars.len() {
        if chars[i] != '#' {
            continue;
        }
        let mut j = i + 1;
        while j < chars.len() && chars[j].is_whitespace() {
            j += 1;
        }
        if !starts_with_at(&chars, j, "flynt:") {
            continue;
        }
        j += 6;
        while j < chars.len() && chars[j].is_whitespace() {
            j += 1;
        }
        if starts_with_at(&chars, j, "skip") {
            return true;
        }
    }
    false
}

/// Line/column coordinates of a chunk, with **byte** columns (converted to char
/// indices on demand, matching Python's `col_offset`/`_byte_to_char_idx`).
struct Coords {
    start_line: usize,
    start_col: usize,
    end_line: usize,
    end_col: usize,
    n_lines: usize,
}

/// The stateful edit cursor. Consumed by `edit`, so — unlike the Python
/// `used_up` guard — it structurally cannot be run twice.
struct EditEngine<'a> {
    src_lines: Vec<&'a str>,
    /// Byte offset in `code` where each `src_lines[i]` begins.
    line_byte_starts: Vec<usize>,
    len_limit: usize,
    results: Vec<String>,
    count_expressions: usize,
    last_line: usize,
    /// Char index into `src_lines[last_line]` (Python `last_idx`).
    last_idx: usize,
}

impl<'a> EditEngine<'a> {
    fn new(code: &'a str, len_limit: Option<usize>) -> Self {
        let src_lines: Vec<&str> = code.split('\n').collect();
        let mut line_byte_starts = Vec::with_capacity(src_lines.len());
        let mut acc = 0usize;
        for line in &src_lines {
            line_byte_starts.push(acc);
            acc += line.len() + 1; // +1 for the '\n' separator
        }
        Self {
            src_lines,
            line_byte_starts,
            // Python maps None -> sys.maxsize; usize::MAX serves the same role.
            len_limit: len_limit.unwrap_or(usize::MAX),
            results: Vec::new(),
            count_expressions: 0,
            last_line: 0,
            last_idx: 0,
        }
    }

    /// Port of `edit`. Fill/try each chunk, append the rest, join, and drop the
    /// final synthetic char (Python `"".join(results)[:-1]`).
    fn edit<F>(mut self, chunks: Vec<Chunk>, state: &mut State, mut transform_func: F) -> (String, usize)
    where
        F: FnMut(&Expr, &mut State, QuoteType) -> (String, bool),
    {
        for chunk in &chunks {
            let coords = self.coords(chunk);
            self.fill_up_to(&coords);
            self.try_chunk(chunk, &coords, state, &mut transform_func);
        }
        self.add_rest();
        let mut out: String = self.results.concat();
        out.pop();
        (out, self.count_expressions)
    }

    /// Byte offset -> `(line, byte_col)`.
    fn locate(&self, byte: usize) -> (usize, usize) {
        let i = self.line_byte_starts.partition_point(|&s| s <= byte) - 1;
        (i, byte - self.line_byte_starts[i])
    }

    fn coords(&self, chunk: &Chunk) -> Coords {
        let (start_line, start_col) = self.locate(usize::from(chunk.range.start()));
        let (end_line, end_col) = self.locate(usize::from(chunk.range.end()));
        Coords {
            start_line,
            start_col,
            end_line,
            end_col,
            n_lines: 1 + end_line - start_line,
        }
    }

    /// Port of `_byte_to_char_idx`: char count of the first `byte_idx` bytes.
    fn byte_to_char_idx(&self, line_no: usize, byte_idx: usize) -> usize {
        self.src_lines[line_no][..byte_idx].chars().count()
    }

    /// Port of `code_between` (byte columns in, char-sliced source out).
    fn code_between(&self, sl: usize, sc: usize, el: usize, ec: usize) -> String {
        if sl == el {
            let s = self.byte_to_char_idx(sl, sc);
            let e = self.byte_to_char_idx(el, ec);
            cslice(self.src_lines[sl], s, e)
        } else {
            let mut parts: Vec<String> = Vec::new();
            let s = self.byte_to_char_idx(sl, sc);
            parts.push(cslice_from(self.src_lines[sl], s));
            for line in (sl + 1)..el {
                parts.push(self.src_lines[line].to_string());
            }
            let e = self.byte_to_char_idx(el, ec);
            parts.push(cslice(self.src_lines[el], 0, e));
            parts.join("\n")
        }
    }

    fn code_in_chunk(&self, c: &Coords) -> String {
        self.code_between(c.start_line, c.start_col, c.end_line, c.end_col)
    }

    /// Port of `fill_up_to` (+ inlined `fill_up_to_line`).
    fn fill_up_to(&mut self, c: &Coords) {
        let start_line = c.start_line;
        let start_idx = self.byte_to_char_idx(c.start_line, c.start_col);
        if start_line == self.last_line {
            self.results
                .push(cslice(self.src_lines[self.last_line], self.last_idx, start_idx));
        } else {
            self.results
                .push(format!("{}\n", cslice_from(self.src_lines[self.last_line], self.last_idx)));
            self.last_line += 1;
            while self.last_line < start_line {
                self.results.push(format!("{}\n", self.src_lines[self.last_line]));
                self.last_line += 1;
            }
            self.results.push(cslice(self.src_lines[start_line], 0, start_idx));
        }
        self.last_idx = start_idx;
    }

    /// Port of `try_chunk`: preflight skips, then transform + maybe_replace.
    fn try_chunk<F>(&mut self, chunk: &Chunk, c: &Coords, state: &mut State, transform_func: &mut F)
    where
        F: FnMut(&Expr, &mut State, QuoteType) -> (String, bool),
    {
        let snippet = self.code_in_chunk(c);

        // A comment anywhere in the chunk aborts the edit.
        if contains_comment(&snippet) {
            return;
        }

        // Prefix inspection on the left-stripped snippet: `[furbFURB]*(quote)`.
        let stripped = snippet.trim_start();
        let prefix = get_string_prefix(stripped);
        let after_prefix = &stripped[prefix.len()..];
        let mut is_raw = false;
        if after_prefix.starts_with('\'') || after_prefix.starts_with('"') {
            let lower = prefix.to_lowercase();
            if lower.contains('b') {
                return;
            }
            is_raw = lower.contains('r');
        }

        // Any physical line intersecting the chunk with a skip comment aborts.
        for line_no in c.start_line..=c.end_line {
            let line = self.src_lines[line_no];
            if noqa_match(line) || flynt_skip_match(line) {
                return;
            }
        }

        // Quote detection on the unstripped snippet; on failure fall back to
        // double quote and an empty escape map (Python's try/except).
        let (quote_type, escape_map) = match (get_quote_type(&snippet), unicode_escape_map(&snippet))
        {
            (Ok(q), Ok(m)) => (q, m),
            _ => (QuoteType::Double, HashMap::new()),
        };

        let (mut converted, changed) = transform_func(&chunk.node, state, quote_type);
        if changed && !escape_map.is_empty() && !is_raw {
            converted = apply_unicode_escape_map(&converted, escape_map);
        }
        if changed {
            let contract_lines = c.n_lines - 1;
            // Source text after the candidate on its end line.
            let end_line = c.start_line + contract_lines; // == c.end_line
            let end_c = self.byte_to_char_idx(end_line, c.end_col);
            let rest = cslice_from(self.src_lines[end_line], end_c);
            self.maybe_replace(c, contract_lines, converted, rest, is_raw);
        }
    }

    /// Port of `maybe_replace`: line-length gate, raw handling, append, then the
    /// redundant-parenthesis peephole.
    fn maybe_replace(
        &mut self,
        c: &Coords,
        contract_lines: usize,
        mut converted: String,
        rest: String,
        is_raw: bool,
    ) {
        let start_char_col = self.byte_to_char_idx(c.start_line, c.start_col);

        // `len(line) <= len_limit - start_col`  <=>  `len(line) + start_col <= len_limit`
        // (rearranged to stay non-negative when len_limit is 0 or usize::MAX).
        let lines_fit = if contract_lines != 0 {
            let snippet_quote = get_quote_type(&self.code_in_chunk(c)).ok();
            if matches!(
                snippet_quote,
                Some(QuoteType::TripleDouble) | Some(QuoteType::TripleSingle)
            ) {
                let mut lines: Vec<String> = converted.split("\\n").map(|s| s.to_string()).collect();
                let last = lines.len() - 1;
                lines[last].push_str(&rest);
                let fit = lines.iter().all(|l| clen(l) + start_char_col <= self.len_limit);
                converted = converted.replace("\\n", "\n");
                fit
            } else {
                clen(&converted) + clen(&rest) + start_char_col <= self.len_limit
            }
        } else {
            true
        };

        if contract_lines != 0 && !lines_fit {
            // Python logs a warning here; message content is not asserted by any
            // golden test and no log crate is a dependency, so this is a no-op.
            return;
        }

        if is_raw {
            converted = converted.replace("\\\\", "\\");
            if !(converted.starts_with('r') || converted.starts_with('R')) {
                converted = format!("r{converted}");
            }
        }

        self.results.push(converted);
        self.count_expressions += 1;
        self.last_line += contract_lines;
        self.last_idx = self.byte_to_char_idx(c.end_line, c.end_col);

        // --- redundant parenthesis removal ---
        if self.results.len() < 2 {
            return;
        }
        let prev_idx = self.results.len() - 2;
        if self.results[prev_idx].is_empty() {
            return;
        }
        if clen(self.src_lines[self.last_line]) == self.last_idx {
            return;
        }
        let prev_last = self.results[prev_idx].chars().last();
        let next_char = char_at(self.src_lines[self.last_line], self.last_idx);
        if prev_last == Some('(') && next_char == Some(')') {
            let prev_chars: Vec<char> = self.results[prev_idx].chars().collect();
            // reversed(prev[:-1]): keep parens only on hitting a disqualifier.
            let mut keep = false;
            for &ch in prev_chars[..prev_chars.len() - 1].iter().rev() {
                if is_py_whitespace(ch) {
                    continue;
                }
                if matches!(ch, '(' | '=' | '[' | '+' | '*') {
                    break;
                }
                keep = true;
                break;
            }
            if keep {
                return;
            }
            self.results[prev_idx] = prev_chars[..prev_chars.len() - 1].iter().collect();
            self.last_idx += 1;
        }
    }

    /// Port of `add_rest`: emit the tail of the current line and every line after.
    fn add_rest(&mut self) {
        self.results
            .push(format!("{}\n", cslice_from(self.src_lines[self.last_line], self.last_idx)));
        self.last_line += 1;
        while self.src_lines.len() > self.last_line {
            self.results.push(format!("{}\n", self.src_lines[self.last_line]));
            self.last_line += 1;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::astutils::parse_expr;
    use ruff_text_size::{TextRange, TextSize};

    /// Build a chunk covering the first occurrence of `sub` in `code`. The node
    /// is a dummy — the edit engine slices the source by range and calls the
    /// (fake) transform, which ignores the node.
    fn chunk_for(code: &str, sub: &str) -> Chunk {
        let start = code.find(sub).expect("substring present");
        let range = TextRange::new(
            TextSize::from(start as u32),
            TextSize::from((start + sub.len()) as u32),
        );
        Chunk::new(parse_expr("a").unwrap(), range)
    }

    /// Drive the engine directly with injected chunks + a constant fake
    /// transform, so these tests do not depend on candidates/transform modules.
    fn run(code: &str, len_limit: Option<usize>, chunks: Vec<Chunk>, repl: &str, changed: bool) -> (String, usize) {
        let mut state = State::default();
        let repl = repl.to_string();
        EditEngine::new(code, len_limit).edit(chunks, &mut state, |_n, _s, _q| (repl.clone(), changed))
    }

    // Reference values below are pinned against flynt 1.0.6's CodeEditor driven
    // with the same fake transform (see task report).

    #[test]
    fn paren_removed_after_assignment() {
        let code = "x = ('a' % b)";
        let out = run(code, None, vec![chunk_for(code, "'a' % b")], "REPL", true);
        assert_eq!(out, ("x = REPL".to_string(), 1));
    }

    #[test]
    fn paren_kept_after_return() {
        // Scanning back hits 'n' of `return` -> disqualified -> parens kept.
        let code = "return ('a' % b)";
        let out = run(code, None, vec![chunk_for(code, "'a' % b")], "REPL", true);
        assert_eq!(out, ("return (REPL)".to_string(), 1));
    }

    #[test]
    fn no_paren_context() {
        let code = "y = 'a' % b";
        let out = run(code, None, vec![chunk_for(code, "'a' % b")], "REPL", true);
        assert_eq!(out, ("y = REPL".to_string(), 1));
    }

    #[test]
    fn unchanged_leaves_source_untouched() {
        let code = "y = 'a' % b";
        let out = run(code, None, vec![chunk_for(code, "'a' % b")], "REPL", false);
        assert_eq!(out, ("y = 'a' % b".to_string(), 0));
    }

    #[test]
    fn final_newline_preserved() {
        let code = "y = 'a' % b\n";
        let out = run(code, None, vec![chunk_for(code, "'a' % b")], "R", true);
        assert_eq!(out, ("y = R\n".to_string(), 1));
    }

    #[test]
    fn two_candidates_one_line() {
        // Two edits on one line, no paren removal ('[' precedes, not '(').
        let code = "sheet['B%s' % i : 'E%s' % i]";
        let chunks = vec![chunk_for(code, "'B%s' % i"), chunk_for(code, "'E%s' % i")];
        let out = run(code, None, chunks, "X", true);
        assert_eq!(out, ("sheet[X : X]".to_string(), 2));
    }

    #[test]
    fn multibyte_offsets_before_chunk() {
        // The degree signs are 2 bytes each; slicing must stay char-correct.
        let code = "print(\"°°\" + (\"a\" % b))";
        let out = run(code, None, vec![chunk_for(code, "\"a\" % b")], "REPL", true);
        assert_eq!(out, ("print(\"°°\" + REPL)".to_string(), 1));
    }

    #[test]
    fn multiline_non_triple_contracts() {
        let code = "z = ('a' %\n b)";
        let out = run(code, None, vec![chunk_for(code, "'a' %\n b")], "REPL", true);
        assert_eq!(out, ("z = REPL".to_string(), 1));
    }

    #[test]
    fn multiline_non_triple_skipped_when_too_long() {
        let code = "z = ('a' %\n b)";
        let out = run(code, Some(1), vec![chunk_for(code, "'a' %\n b")], "REPL", true);
        assert_eq!(out, ("z = ('a' %\n b)".to_string(), 0));
    }

    #[test]
    fn single_line_ignores_length_limit() {
        // contract_lines == 0 -> lines_fit is always true, len limit not checked.
        let code = "y = 'a' % b";
        let out = run(code, Some(1), vec![chunk_for(code, "'a' % b")], "REPLACEMENTLONG", true);
        assert_eq!(out, ("y = REPLACEMENTLONG".to_string(), 1));
    }

    #[test]
    fn triple_quote_contracts_keeping_physical_lines() {
        let code = "\"\"\"line1\n{}\nline3\"\"\".format(x)";
        // Converted carries literal `\n`; the triple branch turns them into real
        // newlines and keeps the physical lines.
        let out = run(code, None, vec![chunk_for(code, code)], "f\"\"\"A\\nB\\nC\"\"\"", true);
        assert_eq!(out, ("f\"\"\"A\nB\nC\"\"\"".to_string(), 1));
    }

    #[test]
    fn triple_quote_skipped_when_a_line_exceeds_limit() {
        let code = "\"\"\"line1\n{}\nline3\"\"\".format(x)";
        let out = run(code, Some(3), vec![chunk_for(code, code)], "f\"\"\"A\\nBBBBB\\nC\"\"\"", true);
        assert_eq!(out, (code.to_string(), 0));
    }

    #[test]
    fn triple_quote_accepted_under_generous_limit() {
        let code = "\"\"\"line1\n{}\nline3\"\"\".format(x)";
        let out = run(code, Some(200), vec![chunk_for(code, code)], "f\"\"\"A\\nBBBBB\\nC\"\"\"", true);
        assert_eq!(out, ("f\"\"\"A\nBBBBB\nC\"\"\"".to_string(), 1));
    }

    #[test]
    fn multiline_cross_line_paren_removal_with_trailing_rest() {
        // `a = ('foo {}'.format(\n    var)).bar` -> the outer `(...)` collapses
        // and the trailing `.bar` (after the skipped `)`) is preserved.
        let code = "a = ('foo {}'.format(\n    var)).bar";
        let out = run(code, None, vec![chunk_for(code, "'foo {}'.format(\n    var)")], "REPL", true);
        assert_eq!(out, ("a = REPL.bar".to_string(), 1));
    }

    #[test]
    fn multiline_start_on_own_line_keeps_parens() {
        // The fragment before the chunk is the line's leading whitespace, not
        // `(` (which is on the previous physical line), so parens stay.
        let code = "a = (\n 'foo {}'.format(var)\n)";
        let out = run(code, None, vec![chunk_for(code, "'foo {}'.format(var)")], "REPL", true);
        assert_eq!(out, ("a = (\n REPL\n)".to_string(), 1));
    }

    #[test]
    fn byte_prefix_is_skipped() {
        let code = "b'%s' % b";
        let out = run(code, None, vec![chunk_for(code, "b'%s' % b")], "REPL", true);
        assert_eq!(out, ("b'%s' % b".to_string(), 0));
    }

    #[test]
    fn comment_in_chunk_is_skipped() {
        let code = "x = ('a'  # c\n % b)";
        let out = run(code, None, vec![chunk_for(code, "'a'  # c\n % b")], "REPL", true);
        assert_eq!(out, (code.to_string(), 0));
    }

    #[test]
    fn noqa_flynt_is_skipped() {
        let code = "a = 'x' % v  # noqa: flynt";
        let out = run(code, None, vec![chunk_for(code, "'x' % v")], "REPL", true);
        assert_eq!(out, (code.to_string(), 0));
    }

    #[test]
    fn flynt_skip_is_skipped() {
        let code = "a = 'x' % v  # flynt: skip";
        let out = run(code, None, vec![chunk_for(code, "'x' % v")], "REPL", true);
        assert_eq!(out, (code.to_string(), 0));
    }

    #[test]
    fn raw_prefix_readded_and_backslashes_collapsed() {
        // Non-raw converted gets an `r` prefix; `\\` collapses to `\`.
        let code = "r'%s' % b";
        let out = run(code, None, vec![chunk_for(code, "r'%s' % b")], "f'X'", true);
        assert_eq!(out, ("rf'X'".to_string(), 1));

        let out = run(code, None, vec![chunk_for(code, "r'%s' % b")], "f'\\\\n'", true);
        // f'\\n' -> collapse -> f'\n' -> prefix -> rf'\n'
        assert_eq!(out, ("rf'\\n'".to_string(), 1));
    }

    #[test]
    fn escape_map_reapplied_to_converted() {
        // The source escape `°` decodes to '°'; the fake output's real '°'
        // is restored to `°`.
        let code = "x = \"pre\\u00B0post\" % y";
        let out = run(code, None, vec![chunk_for(code, "\"pre\\u00B0post\" % y")], "f\"A°B\"", true);
        assert_eq!(out, ("x = f\"A\\u00B0B\"".to_string(), 1));
    }

    #[test]
    fn empty_input_stays_empty() {
        let out = run("", None, vec![], "REPL", true);
        assert_eq!(out, (String::new(), 0));
    }

    #[test]
    fn noqa_and_skip_matchers() {
        assert!(noqa_match("code  # noqa: flynt"));
        assert!(noqa_match("code  #noqa W1, flynt"));
        assert!(!noqa_match("code  # noqa"));
        assert!(!noqa_match("code  # type: ignore"));
        assert!(flynt_skip_match("code  # flynt: skip"));
        assert!(flynt_skip_match("code  #flynt:skip"));
        assert!(!flynt_skip_match("code  # flynt skip"));
    }
}
