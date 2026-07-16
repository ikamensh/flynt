//! Port of src/flynt/linting/fstr_lint.py (FstrInliner).
//! Owner: task #4 (core utils).
//!
//! `FstrInliner` is an `ast.NodeTransformer`: for every f-string it flattens any
//! replacement field whose value is *itself* an f-string with no format spec,
//! splicing that inner f-string's elements into the outer one. It then recurses
//! into all children (Python `generic_visit`).

use ruff_python_ast::{Expr, FStringPart, InterpolatedStringElement, InterpolatedStringElements};

/// Inline nested f-strings inside a JoinedStr (Python: FstrInliner visitor).
pub fn inline_fstrings(node: &mut Expr) {
    // visit_JoinedStr: flatten this node first (matches the transformer, which
    // rewrites `node.values` before calling `generic_visit`).
    if let Expr::FString(fstring) = node {
        for part in fstring.value.iter_mut() {
            if let FStringPart::FString(f) = part {
                flatten_elements(f);
            }
        }
    }
    // generic_visit: recurse into every child expression.
    for_each_child_expr_mut(node, &mut inline_fstrings);
}

/// Rewrite `f.elements`, splicing in the elements of any interpolation whose
/// value is a plain f-string with no format spec.
fn flatten_elements(f: &mut ruff_python_ast::FString) {
    let mut new_elements: Vec<InterpolatedStringElement> = Vec::new();
    for element in f.elements.iter() {
        if let InterpolatedStringElement::Interpolation(interp) = element {
            if interp.format_spec.is_none() {
                if let Expr::FString(inner) = interp.expression.as_ref() {
                    for part in inner.value.iter() {
                        if let FStringPart::FString(inner_f) = part {
                            new_elements.extend(inner_f.elements.iter().cloned());
                        }
                        // A `FStringPart::Literal` (plain-string concat part) has
                        // no direct InterpolatedStringElement analogue; such parts
                        // do not occur in flynt-built trees.
                    }
                    continue;
                }
            }
        }
        new_elements.push(element.clone());
    }
    f.elements = InterpolatedStringElements::from(new_elements);
}

/// Apply `f` to every direct child expression of `expr` (Python `generic_visit`
/// restricted to expressions — the only nodes that can carry an f-string in
/// flynt's trees). Shared with `astutils` for quote normalization.
pub(crate) fn for_each_child_expr_mut(expr: &mut Expr, f: &mut dyn FnMut(&mut Expr)) {
    match expr {
        Expr::BoolOp(e) => e.values.iter_mut().for_each(f),
        Expr::Named(e) => {
            f(&mut e.target);
            f(&mut e.value);
        }
        Expr::BinOp(e) => {
            f(&mut e.left);
            f(&mut e.right);
        }
        Expr::UnaryOp(e) => f(&mut e.operand),
        Expr::Lambda(e) => f(&mut e.body),
        Expr::If(e) => {
            f(&mut e.test);
            f(&mut e.body);
            f(&mut e.orelse);
        }
        Expr::Dict(e) => {
            for item in &mut e.items {
                if let Some(key) = item.key.as_mut() {
                    f(key);
                }
                f(&mut item.value);
            }
        }
        Expr::Set(e) => e.elts.iter_mut().for_each(f),
        Expr::ListComp(e) => {
            f(&mut e.elt);
            for g in &mut e.generators {
                f(&mut g.iter);
                g.ifs.iter_mut().for_each(&mut *f);
            }
        }
        Expr::SetComp(e) => {
            f(&mut e.elt);
            for g in &mut e.generators {
                f(&mut g.iter);
                g.ifs.iter_mut().for_each(&mut *f);
            }
        }
        Expr::DictComp(e) => {
            f(&mut e.key);
            f(&mut e.value);
            for g in &mut e.generators {
                f(&mut g.iter);
                g.ifs.iter_mut().for_each(&mut *f);
            }
        }
        Expr::Generator(e) => {
            f(&mut e.elt);
            for g in &mut e.generators {
                f(&mut g.iter);
                g.ifs.iter_mut().for_each(&mut *f);
            }
        }
        Expr::Await(e) => f(&mut e.value),
        Expr::Yield(e) => {
            if let Some(v) = e.value.as_mut() {
                f(v);
            }
        }
        Expr::YieldFrom(e) => f(&mut e.value),
        Expr::Compare(e) => {
            f(&mut e.left);
            e.comparators.iter_mut().for_each(f);
        }
        Expr::Call(e) => {
            f(&mut e.func);
            e.arguments.args.iter_mut().for_each(&mut *f);
            for kw in &mut e.arguments.keywords {
                f(&mut kw.value);
            }
        }
        Expr::FString(e) => {
            for part in e.value.iter_mut() {
                if let FStringPart::FString(fs) = part {
                    for element in &mut fs.elements {
                        if let InterpolatedStringElement::Interpolation(interp) = element {
                            f(&mut interp.expression);
                            if let Some(spec) = interp.format_spec.as_mut() {
                                for spec_el in &mut spec.elements {
                                    if let InterpolatedStringElement::Interpolation(si) = spec_el {
                                        f(&mut si.expression);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        Expr::Subscript(e) => {
            f(&mut e.value);
            f(&mut e.slice);
        }
        Expr::Starred(e) => f(&mut e.value),
        Expr::Attribute(e) => f(&mut e.value),
        Expr::List(e) => e.elts.iter_mut().for_each(f),
        Expr::Tuple(e) => e.elts.iter_mut().for_each(f),
        Expr::Slice(e) => {
            if let Some(v) = e.lower.as_mut() {
                f(v);
            }
            if let Some(v) = e.upper.as_mut() {
                f(v);
            }
            if let Some(v) = e.step.as_mut() {
                f(v);
            }
        }
        // Leaves and nodes that cannot contain an f-string in flynt's output.
        _ => {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::astutils::{ast_to_string, parse_expr};

    fn inline_str(src: &str) -> String {
        let mut node = parse_expr(src).unwrap();
        inline_fstrings(&mut node);
        ast_to_string(&node).unwrap()
    }

    #[test]
    fn inlines_nested_fstring() {
        // f"{f'{x}'}" -> f"{x}"
        assert_eq!(inline_str("f\"{f'{x}'}\""), "f'{x}'");
    }

    #[test]
    fn inlines_with_surrounding_text() {
        // f"a{f'b{x}c'}d" -> f"ab{x}cd"
        assert_eq!(inline_str("f\"a{f'b{x}c'}d\""), "f'ab{x}cd'");
    }

    #[test]
    fn keeps_nested_with_format_spec() {
        // A nested f-string value WITH a format spec is not inlined: inlining is
        // a no-op, so the unparse is identical with or without it.
        let src = "f\"{f'{x}':>10}\"";
        let mut with = parse_expr(src).unwrap();
        inline_fstrings(&mut with);
        let without = parse_expr(src).unwrap();
        assert_eq!(
            ast_to_string(&with).unwrap(),
            ast_to_string(&without).unwrap()
        );
    }

    #[test]
    fn leaves_plain_fstring() {
        assert_eq!(inline_str("f'{x}{y}'"), "f'{x}{y}'");
    }
}
