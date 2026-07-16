//! Port of src/flynt/string_concat/ (candidates.py, transformer.py,
//! string_in_string.py). Owner: task #8 (codex).

use ruff_python_ast::visitor::{walk_expr, walk_interpolated_string_element, Visitor};
use ruff_python_ast::{
    AtomicNodeIndex, Expr, ExprBinOp, FStringPart, InterpolatedStringElement, Operator,
};
use ruff_text_size::{Ranged, TextRange};

use crate::astutils::{
    ast_formatted_value, ast_string_node, fixup_transformed, new_joined_str, new_string_literal,
};
use crate::chunk::Chunk;
use crate::error::FlyntError;
use crate::quotes::QuoteType;
use crate::state::State;

/// Finds outermost addition trees containing a string literal or f-string.
///
/// The matched outer tree suppresses its nested additions, so candidates are
/// non-overlapping and can be edited in source order.
///
/// ```
/// use flynt_rs::{concat::concat_candidates, state::State};
///
/// let mut state = State::default();
/// let candidates = concat_candidates("value = 'a' + b + 'c'", &mut state);
/// assert_eq!(candidates.len(), 1);
/// assert_eq!(state.concat_candidates, 1);
/// ```
pub fn concat_candidates(code: &str, state: &mut State) -> Vec<Chunk> {
    let Ok(parsed) = ruff_python_parser::parse_module(code) else {
        return Vec::new();
    };
    let mut hound = ConcatHound::default();
    hound.visit_body(&parsed.syntax().body);
    hound.victims.sort_by_key(|chunk| chunk.range.start());
    state.concat_candidates += hound.victims.len();
    hound.victims
}

fn is_string_concat(node: &Expr) -> bool {
    match node {
        Expr::StringLiteral(_) | Expr::FString(_) => true,
        Expr::BinOp(binop) if binop.op == Operator::Add => {
            is_string_concat(&binop.left) || is_string_concat(&binop.right)
        }
        _ => false,
    }
}

#[derive(Default)]
struct ConcatHound {
    victims: Vec<Chunk>,
}

impl<'a> Visitor<'a> for ConcatHound {
    fn visit_expr(&mut self, node: &'a Expr) {
        if matches!(node, Expr::BinOp(_)) && is_string_concat(node) {
            self.victims.push(Chunk::new(node.clone(), node.range()));
        } else {
            walk_expr(self, node);
        }
    }
}

/// Port of string_concat/transformer.py::transform_concat.
pub fn transform_concat(node: &Expr, _state: &mut State, _quote_type: QuoteType) -> (String, bool) {
    let mut transformer = ConcatTransformer::default();
    let Ok(transformed) = transformer.visit(node.clone()) else {
        return (String::new(), false);
    };
    if transformer.counter == 0 {
        return (String::new(), false);
    }

    let target_quote = matches!(transformed, Expr::FString(_) | Expr::StringLiteral(_))
        .then_some(QuoteType::Double);
    match fixup_transformed(transformed, target_quote) {
        Ok(code) => (code, true),
        Err(_) => (String::new(), false),
    }
}

#[derive(Default)]
struct ConcatTransformer {
    counter: usize,
}

impl ConcatTransformer {
    fn visit(&mut self, node: Expr) -> Result<Expr, FlyntError> {
        if matches!(node, Expr::BinOp(_)) && is_string_concat(&node) {
            self.visit_string_binop(node)
        } else {
            self.generic_visit(node)
        }
    }

    fn generic_visit(&mut self, mut node: Expr) -> Result<Expr, FlyntError> {
        let mut error = None;
        crate::fstr_lint::for_each_child_expr_mut(&mut node, &mut |child| {
            if error.is_some() {
                return;
            }
            match self.visit(child.clone()) {
                Ok(transformed) => *child = transformed,
                Err(err) => error = Some(err),
            }
        });
        match error {
            Some(err) => Err(err),
            None => Ok(node),
        }
    }

    fn visit_string_binop(&mut self, node: Expr) -> Result<Expr, FlyntError> {
        let original = node.clone();
        let mut raw_parts = Vec::new();
        unpack_binop(node, &mut raw_parts);

        let mut visited_parts = Vec::with_capacity(raw_parts.len());
        for part in raw_parts {
            visited_parts.push(self.visit(part)?);
        }

        if visited_parts.iter().any(|part| !check_sns_depth(part, 1)) {
            return Ok(rebuild_addition(visited_parts));
        }

        let mut segments = Vec::new();
        for part in visited_parts {
            match part {
                Expr::StringLiteral(string) => {
                    segments.push(ast_string_node(string.value.to_str()));
                }
                Expr::FString(fstring) => {
                    for part in fstring.value.iter() {
                        match part {
                            FStringPart::Literal(literal) => {
                                segments.push(ast_string_node(&literal.value));
                            }
                            FStringPart::FString(fstring) => {
                                segments.extend(fstring.elements.iter().cloned());
                            }
                        }
                    }
                }
                expression => segments.push(ast_formatted_value(expression, None, None)?),
            }
        }

        let has_expr = segments
            .iter()
            .any(|part| matches!(part, InterpolatedStringElement::Interpolation(_)));
        if has_expr && contains_decoded_backslash(&original) {
            return self.generic_visit(original);
        }

        let transformed = if segments
            .iter()
            .all(|part| matches!(part, InterpolatedStringElement::Literal(_)))
        {
            let mut value = String::new();
            for part in segments {
                let InterpolatedStringElement::Literal(literal) = part else {
                    unreachable!();
                };
                value.push_str(&literal.value);
            }
            new_string_literal(&value)
        } else {
            new_joined_str(segments)
        };
        self.counter += 1;
        Ok(transformed)
    }
}

fn unpack_binop(node: Expr, result: &mut Vec<Expr>) {
    match node {
        Expr::BinOp(binop) if binop.op == Operator::Add => {
            unpack_binop(*binop.left, result);
            unpack_binop(*binop.right, result);
        }
        other => result.push(other),
    }
}

fn rebuild_addition(mut parts: Vec<Expr>) -> Expr {
    let mut result = parts.remove(0);
    for part in parts {
        result = Expr::BinOp(ExprBinOp {
            node_index: AtomicNodeIndex::default(),
            range: TextRange::default(),
            left: Box::new(result),
            op: Operator::Add,
            right: Box::new(part),
        });
    }
    result
}

fn check_sns_depth(node: &Expr, limit: usize) -> bool {
    struct DepthDetector {
        depth: usize,
        limit: usize,
        too_deep: bool,
    }

    impl<'a> Visitor<'a> for DepthDetector {
        fn visit_expr(&mut self, node: &'a Expr) {
            if let Expr::FString(fstring) = node {
                self.depth += 1;
                self.too_deep |= self.depth > self.limit;
                for element in fstring.value.elements() {
                    if let InterpolatedStringElement::Interpolation(interpolation) = element {
                        self.visit_expr(&interpolation.expression);
                    }
                }
                self.depth -= 1;
            } else {
                walk_expr(self, node);
            }
        }
    }

    let mut detector = DepthDetector {
        depth: 0,
        limit,
        too_deep: false,
    };
    detector.visit_expr(node);
    !detector.too_deep
}

fn contains_decoded_backslash(node: &Expr) -> bool {
    #[derive(Default)]
    struct BackslashDetector {
        found: bool,
    }

    impl<'a> Visitor<'a> for BackslashDetector {
        fn visit_expr(&mut self, node: &'a Expr) {
            if let Expr::StringLiteral(string) = node {
                self.found |= string.value.to_str().contains('\\');
            }
            walk_expr(self, node);
        }

        fn visit_interpolated_string_element(&mut self, element: &'a InterpolatedStringElement) {
            if let InterpolatedStringElement::Literal(literal) = element {
                self.found |= literal.value.contains('\\');
            }
            walk_interpolated_string_element(self, element);
        }
    }

    let mut detector = BackslashDetector::default();
    detector.visit_expr(node);
    detector.found
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::astutils::parse_expr;

    fn transform(source: &str) -> (String, bool) {
        transform_concat(
            &parse_expr(source).unwrap(),
            &mut State::default(),
            QuoteType::Double,
        )
    }

    #[test]
    fn candidates_find_only_outermost_string_additions_in_source_order() {
        let code = "msg = a + \" World\"\nmsg2 = \"Finally, \" + a + \" World\"\n";
        let mut state = State::default();

        let candidates = concat_candidates(code, &mut state);

        assert_eq!(candidates.len(), 2);
        assert_eq!(state.concat_candidates, 2);
        assert_eq!(
            &code[usize::from(candidates[0].range.start())..usize::from(candidates[0].range.end())],
            "a + \" World\""
        );
        assert_eq!(
            &code[usize::from(candidates[1].range.start())..usize::from(candidates[1].range.end())],
            "\"Finally, \" + a + \" World\""
        );
    }

    #[test]
    fn discovered_candidate_feeds_the_transformer_and_preserves_counter_ownership() {
        let code = "msg = a + \" World\"";
        let mut state = State::default();
        let candidate = concat_candidates(code, &mut state).remove(0);

        let (replacement, changed) =
            transform_concat(&candidate.node, &mut state, QuoteType::Single);

        assert!(changed);
        assert_eq!(replacement, "f\"{a} World\"");
        assert_eq!(state.concat_candidates, 1);
        assert_eq!(state.concat_changes, 0);
        assert_eq!(state.invalid_conversions, 0);
    }

    #[test]
    fn transforms_a_flat_addition_into_one_fstring() {
        assert_eq!(
            transform("a + 'Hello' + b + 'World'"),
            ("f\"{a}Hello{b}World\"".to_string(), true)
        );
    }

    #[test]
    fn transform_matches_python_contracts() {
        let cases = [
            ("'blah' + (thing - 1)", "f\"blah{thing - 1}\""),
            ("'blah' + blah.blah", "f\"blah{blah.blah}\""),
            (
                "'blah' + lst[123].process(x, y, z) + 'Yeah'",
                "f\"blah{lst[123].process(x, y, z)}Yeah\"",
            ),
            (
                "'blah' + blah.blah('more' + vars)",
                "f\"blah{blah.blah(f'more{vars}')}\"",
            ),
            (
                "f'blah{thing}' + otherThing + 'blah'",
                "f\"blah{thing}{otherThing}blah\"",
            ),
            (
                "f'blah{thing}' + otherThing + f'blah{thing + 1}'",
                "f\"blah{thing}{otherThing}blah{thing + 1}\"",
            ),
            (
                "print(f'blah{thing}' + 'blah' + otherThing + f\"is {x:d}\")",
                "print(f'blah{thing}blah{otherThing}is {x:d}')",
            ),
            (
                "print(f\"{f'blah{var}' + abc}blah\")",
                "print(f'blah{var}{abc}blah')",
            ),
            ("blah1 + 'b'", "f\"{blah1}b\""),
            ("\"here\" + r\"\\there\"", "\"here\\\\there\""),
        ];

        for (source, expected) in cases {
            assert_eq!(transform(source), (expected.to_string(), true), "{source}");
        }
    }

    #[test]
    fn excessive_fstring_depth_refuses_outer_concat_but_keeps_inner_changes() {
        let (new, changed) = transform("'blah' + blah.blah('more' + vars.foo('other' + b))");

        assert!(changed);
        assert!(new.contains("'blah' +"), "{new}");
        assert!(new.contains("f'other{b}'"), "{new}");
    }

    #[test]
    fn refuses_expression_concat_when_a_string_contains_a_decoded_backslash() {
        assert_eq!(
            transform(r#"re.sub(r"\.py$", "", test) + ".py""#),
            (String::new(), false)
        );
    }

    #[test]
    fn construction_refusal_returns_empty_and_unchanged() {
        assert_eq!(transform("'prefix' + {1: 2}"), (String::new(), false));
    }
}
