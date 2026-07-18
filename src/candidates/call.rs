//! Port of src/flynt/candidates/ast_call_candidates.py.
//! Owner: task #6 (.format() pipeline).
//!
//! Discovers `"...".format(...)` candidates: `ast.Call` nodes whose `func` is an
//! `ast.Attribute` named exactly `format` on a plain string-literal receiver
//! (`is_call_format`). Matching a node records it and does *not* descend into its
//! receiver or arguments, so the outermost `.format` is the candidate and any
//! nested `.format` inside its arguments is left for the transformer to rewrite
//! recursively (see `transform::fstringify`). Candidates are returned in source
//! order and `state.call_candidates` is incremented by the number found.

use ruff_python_ast::visitor::{walk_expr, Visitor};
use ruff_python_ast::{Expr, Stmt};
use ruff_text_size::Ranged;

use crate::chunk::Chunk;
use crate::state::State;

/// Port of `is_call_format`: a `.format(...)` call on a literal string.
pub fn is_call_format(node: &Expr) -> bool {
    if let Expr::Call(call) = node {
        if let Expr::Attribute(attr) = call.func.as_ref() {
            return attr.attr.as_str() == "format" && crate::astutils::is_str_constant(&attr.value);
        }
    }
    false
}

struct CallFmtFinder {
    candidates: Vec<Chunk>,
}

impl<'a> Visitor<'a> for CallFmtFinder {
    fn visit_expr(&mut self, expr: &'a Expr) {
        if is_call_format(expr) {
            // Record the outermost match and do NOT descend into its children
            // (Python: no `generic_visit`), so nested `.format` calls inside the
            // arguments are not separate candidates.
            self.candidates.push(Chunk::new(expr.clone(), expr.range()));
        } else {
            walk_expr(self, expr);
        }
    }
}

/// Find `"...".format(...)` candidates; increments `state.call_candidates`.
pub fn call_candidates(code: &str, state: &mut State) -> Vec<Chunk> {
    let parsed = match ruff_python_parser::parse_module(code) {
        Ok(p) => p,
        // Python `ast.parse` would raise; the shared pipeline only reaches this
        // with source that already parsed, so treat an error as "no candidates".
        Err(_) => return Vec::new(),
    };

    let mut finder = CallFmtFinder {
        candidates: Vec::new(),
    };
    for stmt in &parsed.syntax().body {
        visit_stmt(&mut finder, stmt);
    }

    // Source order (top-to-bottom, left-to-right). Evaluation-order traversal can
    // yield a different sequence for siblings; CodeEditor requires source order.
    crate::chunk::sort_dedup(&mut finder.candidates);

    state.call_candidates += finder.candidates.len();
    finder.candidates
}

fn visit_stmt(finder: &mut CallFmtFinder, stmt: &Stmt) {
    finder.visit_stmt(stmt);
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names(code: &str) -> (usize, Vec<String>) {
        let mut state = State::default();
        let chunks = call_candidates(code, &mut state);
        let strs = chunks
            .iter()
            .map(|c| crate::astutils::ast_to_string(&c.node).unwrap())
            .collect();
        (state.call_candidates, strs)
    }

    #[test]
    fn finds_literal_format_call() {
        // `ast_to_string` normalizes to single quotes (like `ast.unparse`).
        let (n, s) = names(r#""hello {}".format(x)"#);
        assert_eq!(n, 1);
        assert_eq!(s, vec![r#"'hello {}'.format(x)"#]);
    }

    #[test]
    fn rejects_variable_receiver() {
        // `template.format(...)` — receiver is a Name, not a literal.
        let (n, _) = names("template = 'Hello {0}'\nresult = template.format(name)");
        assert_eq!(n, 0);
    }

    #[test]
    fn rejects_fstring_and_bytes_receiver() {
        assert_eq!(names(r#"f"{a}".format(x)"#).0, 0);
        assert_eq!(names(r#"b"{}".format(x)"#).0, 0);
    }

    #[test]
    fn rejects_non_format_attribute() {
        assert_eq!(names(r#""x".upper()"#).0, 0);
    }

    #[test]
    fn does_not_descend_into_matched_call() {
        // Outer `.format` matches; the inner one inside the argument is NOT a
        // separate candidate (Python does not descend into a matched node).
        let (n, s) = names(r#""Hello {}".format(d["a{}".format(key)])"#);
        assert_eq!(n, 1);
        assert_eq!(s.len(), 1);
    }

    #[test]
    fn two_calls_in_source_order() {
        let (n, s) = names("'{}'.format(a)\n'{}'.format(b)");
        assert_eq!(n, 2);
        assert_eq!(s, vec!["'{}'.format(a)", "'{}'.format(b)"]);
    }

    #[test]
    fn implicit_concat_receiver_is_one_constant() {
        // Adjacent string literals are folded by the parser into one constant.
        let (n, _) = names(r#""Helloo {}" "!!!".format(world)"#);
        assert_eq!(n, 1);
    }
}
