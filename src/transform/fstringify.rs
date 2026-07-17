//! Port of src/flynt/transform/FstringifyTransformer.py + `fstringify_node`.
//! Owner: task #6.
//!
//! `FstringifyTransformer` is CPython's `ast.NodeTransformer` semantics:
//! * a matched `.format` call is rewritten by `joined_string`; the *result* is
//!   then visited again so nested `.format` calls in inserted expressions are
//!   rewritten too; counters advance after the recursive visit;
//! * a matched `str % ...` binop is rewritten by `transform_binop` (owned by the
//!   percent task); its result is NOT revisited;
//! * an unmatched `Call` or `BinOp` returns unchanged WITHOUT descending into its
//!   subtree (Python returns the node without `generic_visit`) — this prunes the
//!   subtree, which is why discovery emits separate chunks per candidate kind;
//! * every other node type is traversed by `generic_visit`, so candidates nested
//!   inside e.g. a `Subscript`/`List`/`FormattedValue` are still found.

use ruff_python_ast::{Expr, Operator};

use crate::astutils::{get_str_value, is_str_constant};
use crate::candidates::call::is_call_format;
use crate::error::FlyntError;
use crate::state::State;
use crate::transform::format_call::{joined_string, scan_constants};
use crate::transform::percent::transform_binop;

struct Transformer<'s> {
    state: &'s mut State,
    counter: usize,
    err: Option<FlyntError>,
}

impl Transformer<'_> {
    fn visit(&mut self, expr: &mut Expr) {
        if self.err.is_some() {
            return;
        }
        match expr {
            Expr::Call(_) => self.visit_call(expr),
            Expr::BinOp(_) => self.visit_binop(expr),
            _ => self.generic_visit(expr),
        }
    }

    fn visit_call(&mut self, expr: &mut Expr) {
        if !(self.state.transform_format && is_call_format(expr)) {
            // Unmatched call: return without descending (subtree pruned).
            return;
        }
        self.state.call_candidates += 1;

        if let Expr::Call(call) = &*expr {
            if call.arguments.args.iter().any(|a| matches!(a, Expr::Starred(_))) {
                // `*args` bail — no way to preserve unpacking semantics.
                return;
            }
        }

        let aggressive = self.state.aggressive >= 1;
        match joined_string(&*expr, aggressive) {
            Ok(mut result) => {
                // Revisit the produced node so nested `.format` calls transform.
                self.visit(&mut result);
                if self.err.is_some() {
                    return;
                }
                self.counter += 1;
                self.state.call_transforms += 1;
                *expr = result;
            }
            Err(e) => self.err = Some(e),
        }
    }

    fn visit_binop(&mut self, expr: &mut Expr) {
        if !(self.state.transform_percent && is_percent_stringify(expr)) {
            return;
        }
        self.state.percent_candidates += 1;

        // Preflight skips (return the node unchanged, no transform):
        if let Expr::BinOp(b) = &*expr {
            if let Ok(left) = get_str_value(&b.left) {
                if left.contains('{') || left.contains('}') {
                    return;
                }
            }
            if rhs_has_unsafe_string(&b.right) {
                return;
            }
        }

        match transform_binop(&*expr, self.state) {
            Ok(result) => {
                self.counter += 1;
                self.state.percent_transforms += 1;
                *expr = result;
            }
            Err(e) => self.err = Some(e),
        }
    }

    fn generic_visit(&mut self, expr: &mut Expr) {
        crate::fstr_lint::for_each_child_expr_mut(expr, &mut |child: &mut Expr| {
            if self.err.is_none() {
                self.visit(child);
            }
        });
    }
}

/// Port of `is_percent_stringify`: literal-left `%` with a supported RHS class.
fn is_percent_stringify(expr: &Expr) -> bool {
    if let Expr::BinOp(b) = expr {
        return is_str_constant(&b.left)
            && matches!(b.op, Operator::Mod)
            && is_supported_percent_rhs(&b.right);
    }
    false
}

fn is_supported_percent_rhs(rhs: &Expr) -> bool {
    matches!(
        rhs,
        Expr::Tuple(_)
            | Expr::List(_)
            | Expr::Dict(_)
            | Expr::Name(_)
            | Expr::Attribute(_)
            | Expr::Subscript(_)
            | Expr::Call(_)
            | Expr::BinOp(_)
            | Expr::If(_)
            // ast.Constant covers all literal kinds in Python.
            | Expr::StringLiteral(_)
            | Expr::BytesLiteral(_)
            | Expr::NumberLiteral(_)
            | Expr::BooleanLiteral(_)
            | Expr::NoneLiteral(_)
            | Expr::EllipsisLiteral(_)
    )
}

/// Preflight for percent: skip when any string constant under the RHS contains a
/// newline/tab/CR/quote/percent/backslash (Python `is_str_constant` also covers
/// f-string literal parts, so those are included via `scan_constants`).
fn rhs_has_unsafe_string(rhs: &Expr) -> bool {
    scan_constants(rhs).strings.iter().any(|v| {
        v.contains('\n')
            || v.contains('\t')
            || v.contains('\r')
            || v.contains('\'')
            || v.contains('"')
            || v.contains('%')
            || v.contains('\\')
    })
}

/// Port of `fstringify_node`: transform on a deep copy, then run `FstrInliner`.
/// Returns `(new_node, changed)`; `changed` is true when at least one candidate
/// was rewritten.
pub fn fstringify_node(node: &Expr, state: &mut State) -> Result<(Expr, bool), FlyntError> {
    let mut tree = node.clone();
    let mut t = Transformer {
        state,
        counter: 0,
        err: None,
    };
    t.visit(&mut tree);
    let err = t.err.take();
    let counter = t.counter;
    drop(t);
    if let Some(e) = err {
        return Err(e);
    }
    crate::fstr_lint::inline_fstrings(&mut tree);
    Ok((tree, counter > 0))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::astutils::{ast_to_string, parse_expr};

    fn run(code: &str) -> (String, bool) {
        let node = parse_expr(code).unwrap();
        let mut state = State::default();
        let (out, changed) = fstringify_node(&node, &mut state).unwrap();
        (ast_to_string(&out).unwrap(), changed)
    }

    #[test]
    fn transforms_simple_format() {
        let (out, changed) = run(r#""{} {}".format(a, b)"#);
        assert!(changed);
        assert_eq!(out, "f'{a} {b}'");
    }

    #[test]
    fn nested_format_in_argument() {
        // The explicit revisit of the result rewrites the inner `.format`.
        // `ast_to_string` picks the outer delimiter like CPython ast.unparse:
        // the field contains single quotes, so the outer quote is `"`.
        let (out, changed) = run(r#""Hello {}".format(d["a{}".format(key)])"#);
        assert!(changed);
        assert_eq!(out, "f\"Hello {d[f'a{key}']}\"");
    }

    #[test]
    fn candidate_counter_increments() {
        let node = parse_expr(r#""Hello {}".format(d["a{}".format(key)])"#).unwrap();
        let mut state = State::default();
        let _ = fstringify_node(&node, &mut state).unwrap();
        // Transformer counts the outer AND the nested `.format` (double-count quirk).
        assert_eq!(state.call_candidates, 2);
        assert_eq!(state.call_transforms, 2);
    }

    #[test]
    fn unmatched_call_is_unchanged() {
        let (_, changed) = run(r#"foo("{}".format)"#);
        // `.format` here is an attribute access, not a call — no candidate.
        assert!(!changed);
    }

    #[test]
    fn disabled_format_transform() {
        let node = parse_expr(r#""{} {}".format(a, b)"#).unwrap();
        let mut state = State {
            transform_format: false,
            ..State::default()
        };
        let (_, changed) = fstringify_node(&node, &mut state).unwrap();
        assert!(!changed);
        assert_eq!(state.call_candidates, 0);
    }

    #[test]
    fn starred_argument_bails() {
        let node = parse_expr(r#""{} {}".format(*a)"#).unwrap();
        let mut state = State::default();
        let (_, changed) = fstringify_node(&node, &mut state).unwrap();
        assert!(!changed);
        // candidate still counted before the bail
        assert_eq!(state.call_candidates, 1);
        assert_eq!(state.call_transforms, 0);
    }
}
