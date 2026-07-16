//! Port of src/flynt/candidates/ast_percent_candidates.py.
//! Owner: task #5 (percent pipeline).

use ruff_python_ast::visitor::{walk_expr, Visitor};
use ruff_python_ast::{Expr, Operator};
use ruff_python_parser::parse_module;

use crate::astutils::is_str_constant;
use crate::chunk::Chunk;
use crate::state::State;

/// Port of `is_percent_format`: `str % ...` where the operator is `%` and the
/// left operand is a plain string constant. The right operand is *not* checked
/// during discovery (so `"%s" % {x}` is discovered even though the transformer
/// later refuses an `ast.Set` RHS).
fn is_percent_format(expr: &Expr) -> bool {
    matches!(
        expr,
        Expr::BinOp(b) if matches!(b.op, Operator::Mod) && is_str_constant(&b.left)
    )
}

/// Port of `PercentFmtFinder`. Records every matched literal-`%` `BinOp` and,
/// like the Python `visit_BinOp`, does *not* descend into a matched node's
/// operands. All other nodes are traversed normally.
struct PercentFmtFinder {
    candidates: Vec<Chunk>,
}

impl<'a> Visitor<'a> for PercentFmtFinder {
    fn visit_expr(&mut self, expr: &'a Expr) {
        if let Expr::BinOp(b) = expr {
            if is_percent_format(expr) {
                self.candidates.push(Chunk::new(expr.clone(), b.range));
                return; // do not visit operands (Python: no generic_visit)
            }
        }
        walk_expr(self, expr);
    }
}

/// Find `str % ...` candidates; increments `state.percent_candidates` by the
/// number found. Returned chunks are ordered by their start position in the
/// source (CodeEditor relies on positional ordering).
pub fn percent_candidates(code: &str, state: &mut State) -> Vec<Chunk> {
    let parsed = match parse_module(code) {
        Ok(p) => p,
        // Python `ast.parse` would raise on a syntax error; the pipeline only
        // ever feeds already-valid source here, so an unparsable input yields
        // no candidates.
        Err(_) => return Vec::new(),
    };

    let mut finder = PercentFmtFinder {
        candidates: Vec::new(),
    };
    for stmt in &parsed.syntax().body {
        finder.visit_stmt(stmt);
    }

    state.percent_candidates += finder.candidates.len();

    let mut chunks = finder.candidates;
    chunks.sort_by_key(|c| c.range.start());
    chunks
}

#[cfg(test)]
mod tests {
    use super::*;

    fn count(code: &str) -> (usize, Vec<String>) {
        let mut state = State::default();
        let chunks = percent_candidates(code, &mut state);
        let spans = chunks
            .iter()
            .map(|c| code[c.range].to_string())
            .collect::<Vec<_>>();
        (state.percent_candidates, spans)
    }

    #[test]
    fn str_newline() {
        // test_candidates::test_str_newline
        let (n, _) = count("a = '%s\\n' % var");
        assert_eq!(n, 1);
    }

    #[test]
    fn percent_attribute_span() {
        // test_candidates::test_percent_attribute
        let code = "src_info = 'application \"%s\"' % srcobj.import_name";
        let (n, spans) = count(code);
        assert_eq!(n, 1);
        assert_eq!(spans[0], "'application \"%s\"' % srcobj.import_name");
    }

    #[test]
    fn percent_call_span() {
        // test_candidates::test_percent_call
        let code = "{\"filename*\": \"UTF-8''%s\" % url_quote(attachment_filename)}";
        let (_, spans) = count(code);
        assert_eq!(spans[0], "\"UTF-8''%s\" % url_quote(attachment_filename)");
    }

    #[test]
    fn discovers_set_rhs() {
        // RHS type is not checked during discovery: "%s" % {x} is a candidate.
        let (n, _) = count("'%s' % {x}");
        assert_eq!(n, 1);
    }

    #[test]
    fn rejects_non_str_left_and_non_mod() {
        assert_eq!(count("var % x").0, 0);
        assert_eq!(count("b'%s' % x").0, 0);
        assert_eq!(count("f'{y}' % x").0, 0);
        assert_eq!(count("'a' + x").0, 0);
    }

    #[test]
    fn does_not_descend_into_matched() {
        // A `%` nested inside a matched outer literal-percent is not a separate
        // candidate. Here the outer is matched; there is no inner percent, but
        // two independent candidates are found and ordered by position.
        let code = "f(a % b, '%s' % c)"; // a % b: left not str -> not matched
        let (n, spans) = count(code);
        assert_eq!(n, 1);
        assert_eq!(spans[0], "'%s' % c");

        let code2 = "x = '%s' % a\ny = '%d' % b";
        let (n2, spans2) = count(code2);
        assert_eq!(n2, 2);
        assert_eq!(spans2, vec!["'%s' % a".to_string(), "'%d' % b".to_string()]);
    }

    #[test]
    fn ordered_by_position() {
        let code = "['%s' % a, '%d' % b, '%r' % c]";
        let (_, spans) = count(code);
        assert_eq!(
            spans,
            vec![
                "'%s' % a".to_string(),
                "'%d' % b".to_string(),
                "'%r' % c".to_string()
            ]
        );
    }
}
