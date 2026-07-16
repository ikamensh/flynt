//! Port of src/flynt/static_join/ (candidates.py, transformer.py, utils.py).
//! Owner: task #8 (codex).

use ruff_python_ast::visitor::{walk_expr, Visitor};
use ruff_python_ast::Expr;
use ruff_text_size::Ranged;

use crate::astutils::{
    ast_formatted_value, ast_string_node, fixup_transformed, new_joined_str, new_string_literal,
};
use crate::chunk::Chunk;
use crate::error::FlyntError;
use crate::quotes::QuoteType;
use crate::state::State;

/// Finds calls with a literal joiner and a static, unstarred container.
///
/// Dynamic iterables remain untouched because their length and elements are
/// not syntactically known.
///
/// ```
/// use flynt_rs::{state::State, static_join::join_candidates};
///
/// let mut state = State::default();
/// let candidates = join_candidates("value = ','.join([left, right])", &mut state);
/// assert_eq!(candidates.len(), 1);
/// assert_eq!(state.join_candidates, 1);
/// ```
pub fn join_candidates(code: &str, state: &mut State) -> Vec<Chunk> {
    let Ok(parsed) = ruff_python_parser::parse_module(code) else {
        return Vec::new();
    };
    let mut hound = JoinHound::default();
    hound.visit_body(&parsed.syntax().body);
    hound.victims.sort_by_key(|chunk| chunk.range.start());
    state.join_candidates += hound.victims.len();
    hound.victims
}

fn get_static_join_bits(node: &Expr) -> Option<(String, Vec<Expr>)> {
    let Expr::Call(call) = node else {
        return None;
    };
    let Expr::Attribute(attribute) = call.func.as_ref() else {
        return None;
    };
    if attribute.attr.as_str() != "join" {
        return None;
    }
    let Expr::StringLiteral(joiner) = attribute.value.as_ref() else {
        // Python accepts f-strings here and then ast.literal_eval raises. This
        // infallible Rust interface represents that case as a clean refusal.
        return None;
    };
    if call.arguments.args.len() != 1 {
        return None;
    }
    let elements = match &call.arguments.args[0] {
        Expr::List(container) => &container.elts,
        Expr::Tuple(container) => &container.elts,
        Expr::Set(container) => &container.elts,
        _ => return None,
    };
    if elements
        .iter()
        .any(|element| matches!(element, Expr::Starred(_)))
    {
        return None;
    }
    Some((joiner.value.to_str().to_string(), elements.clone()))
}

#[derive(Default)]
struct JoinHound {
    victims: Vec<Chunk>,
}

impl<'a> Visitor<'a> for JoinHound {
    fn visit_expr(&mut self, node: &'a Expr) {
        if get_static_join_bits(node).is_some() {
            self.victims.push(Chunk::new(node.clone(), node.range()));
        } else {
            walk_expr(self, node);
        }
    }
}

/// Port of static_join/transformer.py::transform_join.
pub fn transform_join(node: &Expr, _state: &mut State, _quote_type: QuoteType) -> (String, bool) {
    let mut transformer = JoinTransformer::default();
    let Ok(transformed) = transformer.visit(node.clone()) else {
        return (String::new(), false);
    };
    if transformer.counter == 0 {
        return (String::new(), false);
    }
    match fixup_transformed(transformed, Some(QuoteType::Double)) {
        Ok(code) => (code, true),
        Err(_) => (String::new(), false),
    }
}

#[derive(Default)]
struct JoinTransformer {
    counter: usize,
}

impl JoinTransformer {
    fn visit(&mut self, node: Expr) -> Result<Expr, FlyntError> {
        if let Some((joiner, elements)) = get_static_join_bits(&node) {
            self.counter += 1;
            return Self::build_join(joiner, elements);
        }
        self.generic_visit(node)
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

    fn build_join(joiner: String, elements: Vec<Expr>) -> Result<Expr, FlyntError> {
        if elements.is_empty() {
            return Err(FlyntError::ConversionRefused(
                "cannot transform a join over an empty container".to_string(),
            ));
        }

        let mut segments = Vec::with_capacity(elements.len() * 2 - 1);
        let last = elements.len() - 1;
        for (index, element) in elements.into_iter().enumerate() {
            if let Expr::StringLiteral(string) = element {
                segments.push(ast_string_node(string.value.to_str()));
            } else {
                segments.push(ast_formatted_value(element, None, None)?);
            }
            if index != last {
                segments.push(ast_string_node(&joiner));
            }
        }

        if segments
            .iter()
            .all(|part| matches!(part, ruff_python_ast::InterpolatedStringElement::Literal(_)))
        {
            let mut value = String::new();
            for part in segments {
                let ruff_python_ast::InterpolatedStringElement::Literal(literal) = part else {
                    unreachable!();
                };
                value.push_str(&literal.value);
            }
            Ok(new_string_literal(&value))
        } else {
            Ok(new_joined_str(segments))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::astutils::parse_expr;

    fn transform(source: &str) -> (String, bool) {
        transform_join(
            &parse_expr(source).unwrap(),
            &mut State::default(),
            QuoteType::Single,
        )
    }

    #[test]
    fn candidates_accept_only_literal_joiners_and_static_unstarred_containers() {
        let code = concat!(
            "a = 'b'.join(['a', value])\n",
            "b = sep.join(['a', 'b'])\n",
            "c = 'x'.join(item for item in values)\n",
            "d = 'x'.join([head, *tail])\n",
            "e = ''.join(('a', 'b'))\n",
        );
        let mut state = State::default();

        let candidates = join_candidates(code, &mut state);

        assert_eq!(candidates.len(), 2);
        assert_eq!(state.join_candidates, 2);
        assert_eq!(
            &code[usize::from(candidates[0].range.start())..usize::from(candidates[0].range.end())],
            "'b'.join(['a', value])"
        );
        assert_eq!(
            &code[usize::from(candidates[1].range.start())..usize::from(candidates[1].range.end())],
            "''.join(('a', 'b'))"
        );
    }

    #[test]
    fn discovered_refusal_keeps_candidate_and_change_counters_separate() {
        let code = "value = 'a'.join([])";
        let mut state = State::default();
        let candidate = join_candidates(code, &mut state).remove(0);

        let transformed = transform_join(&candidate.node, &mut state, QuoteType::Single);

        assert_eq!(transformed, (String::new(), false));
        assert_eq!(state.join_candidates, 1);
        assert_eq!(state.join_changes, 0);
        assert_eq!(state.invalid_conversions, 0);
    }

    #[test]
    fn transforms_static_join_into_one_fstring() {
        assert_eq!(
            transform("'blah'.join([thing, (thing - 1)])"),
            ("f\"{thing}blah{thing - 1}\"".to_string(), true)
        );
    }

    #[test]
    fn transform_matches_python_contracts() {
        let cases = [
            ("'b'.join(['a', 'c'])", "\"abc\""),
            (
                "'blah'.join([blah.blah, blah.bleh])",
                "f\"{blah.blah}blah{blah.bleh}\"",
            ),
            ("''.join([a, b, 'c'])", "f\"{a}{b}c\""),
            ("\" \".join([a, \"World\"])", "f\"{a} World\""),
            (
                "\"\".join([\"Finally, \", a, \" World\"])",
                "f\"Finally, {a} World\"",
            ),
            ("\"x\".join((\"1\", \"2\", \"3\"))", "\"1x2x3\""),
            ("\"x\".join({\"4\", '5', \"yee\"})", "\"4x5xyee\""),
            ("\"y\".join([1, 2, 3])", "f\"{1}y{2}y{3}\""),
            ("\"a\".join([b])", "f\"{b}\""),
            ("\"x\".join([\"a\", \"b\"], ignored=True)", "\"axb\""),
        ];

        for (source, expected) in cases {
            assert_eq!(transform(source), (expected.to_string(), true), "{source}");
        }
    }

    #[test]
    fn transform_refuses_non_static_and_starred_inputs() {
        for source in [
            "a.join(['1', '2', '3'])",
            "'a'.join(a)",
            "'a'.join([a, a, *a])",
            "'a'.join([c for c in a])",
            "'a'.join()",
            "'a'.join(['x'], ['y'])",
        ] {
            assert_eq!(transform(source), (String::new(), false), "{source}");
        }
    }

    #[test]
    fn transform_turns_original_join_exceptions_into_refusals() {
        for source in ["'a'.join([])", "f'a'.join(['x'])", "'a'.join([{1: 2}])"] {
            assert_eq!(transform(source), (String::new(), false), "{source}");
        }
    }
}
