#!/usr/bin/env python
"""Generate golden fixtures for the .format() pipeline differential tests.

Run with the project venv (from the repo root):
    .venv/bin/python flynt-rust/tests/fixtures/gen_format_fixtures.py

Captures the exact behaviour of flynt 1.0.6's `transform_chunk` (on the *bare
expression node*, matching how `CodeEditor` calls it in the real pipeline) and
`call_candidates` discovery, so the Rust port can be checked byte-for-byte.

Outputs (owned by task #6):
    format_transform.json  — transform_chunk over .format snippets
    call_candidates.json   — call_candidates discovery over whole-code snippets
"""
import ast
import glob
import json
import os

from flynt.state import State
from flynt.transform.transform import transform_chunk
from flynt.utils.format import QuoteTypes
from flynt.candidates.ast_call_candidates import call_candidates
from flynt.utils.utils import ast_to_string

HERE = os.path.dirname(os.path.abspath(__file__))
FLYNT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "flynt"))
SAMPLE_DIRS = [
    os.path.join(FLYNT, "test", "integration", "samples_in"),
    os.path.join(FLYNT, "test", "integration", "expected_out"),
]

QT_NAMES = {
    QuoteTypes.single: "single",
    QuoteTypes.double: "double",
    QuoteTypes.triple_single: "triple_single",
    QuoteTypes.triple_double: "triple_double",
}

# Curated .format snippets: the test_transform.py contract (transform + noop +
# aggressive), plus a few extra edge cases exercised by the SPEC.
CURATED = [
    # --- transforms ---
    '"my string {:.2f}".format(var)',
    '"my string {:.2f}".format(var+1)',
    r'''"echo '{}'\n".format(self.FLUSH_CMD)''',
    '"Flask Documentation ({})".format(version)',
    '"Helloo {}" "!!!".format(world)',
    '"""Flask Documentation ({0})""".format(version)',
    '"Flask Documentation ({1} {0:.2f} {name})".format(version,sprt,name=NAME)',
    '"Failed after {:,}".format(x)',
    '"Search: finished in {0:,} ms.".format(vm.search_time_elapsed_ms)',
    '"{} {}".format(a, b)',
    '"{1} {0}".format(a, b)',
    '"{x.y}".format(x=z)',
    '"{0.y}".format(z)',
    '"{.y}".format(z)',
    '"{.x} {.y}".format(a, b)',
    '"{} {}".format(a.b, c.d)',
    '"hello {}!".format(name)',
    '"{}{{}}{}".format(escaped, y)',
    '"{}{b}{}".format(a, c, b=b)',
    '"{}" . format(x)',
    '"{}".format(\n    a,\n)',
    '"{:{}}".format(x, y)',
    '"{:{fill}}".format(x, fill=c)',
    '"{} {:>{}}".format(a, b, c)',
    '"{}".format(a if b else c)',
    '"{!r}".format(x)',
    '"{!s}".format(x)',
    '"{!a}".format(x)',
    '"{}".format(str(x))',
    '"{}".format(repr(x))',
    '"lit {}".format("const")',
    '"{}".format("only")',
    # --- noop (unchanged) ---
    "'{'.format(a)",
    "'}'.format(a)",
    '"{} {}".format(*a)',
    '"{foo} {bar}".format(**b)',
    '"{0} {0}".format(arg)',
    '"{x} {x}".format(arg)',
    '"{x.y} {x.z}".format(arg)',
    'b"{} {}".format(a, b)',
    '"{a[b]}".format(a=a)',
    '"{a.a[b]}".format(a=a)',
    '"{}{}".format(a)',
    '"{a}{b}".format(a=a)',
    '"{}".format(b"\\n")',
    '"{}".format("\\n".join(items))',
    'msg.format(x)',
    '"{}\\nPossible solutions:\\n{}".format(msg, "\\n".join(solutions))',
    "return_val",  # plain name (no candidate) — exercises changed=False
    # --- aggressive-only ---
    "'{0:>{1}}'.format(bench[prop], widths[prop])",
    '"{0:{1}.{2}f}".format(x, w, p)',
    '"{0:*>{1}}".format(x, n)',
]

# Whole-code snippets for candidate discovery.
CANDIDATE_SNIPPETS = [
    '"hello {}".format(x)',
    "template = 'Hello {0}'\nresult = template.format(name)",
    "'{}'.format(a)\n'{}'.format(b)",
    'f"{a}".format(x)',
    'b"{}".format(x)',
    '"Hello {}".format(d["a{}".format(key)])',
    "x = '{}'.format(1)\ny = '%s' % z\nw = '{}'.format(2)",
    "print('{} and {}'.format(a, b))\n'{}'.format(c)",
    "no_candidates_here = 1 + 2",
    "obj.format(x)",  # `.format` on a non-literal receiver — not a candidate
    "'{}'.upper().format(x)",  # receiver is a call — not a candidate
    "['{}'.format(a), '{}'.format(b)]",  # two candidates inside a list literal
]


def corpus_format_calls():
    """Every `"...".format(...)` Call in the sample corpus, unparsed."""
    seen = set()
    for d in SAMPLE_DIRS:
        for path in sorted(glob.glob(os.path.join(d, "*.py"))):
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            try:
                tree = ast.parse(src)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "format"
                    and isinstance(node.func.value, ast.Constant)
                    and isinstance(node.func.value.value, str)
                ):
                    try:
                        code = ast.unparse(node)
                        ast.parse(code, mode="eval")  # must round-trip
                    except Exception:
                        continue
                    if code not in seen:
                        seen.add(code)
                        yield code


def counters(state):
    return {
        "call_candidates": state.call_candidates,
        "call_transforms": state.call_transforms,
        "percent_candidates": state.percent_candidates,
        "percent_transforms": state.percent_transforms,
        "invalid_conversions": state.invalid_conversions,
    }


def gen_format_transform():
    snippets = list(CURATED)
    seen = set(snippets)
    for code in corpus_format_calls():
        if code not in seen:
            seen.add(code)
            snippets.append(code)

    out = []
    for code in snippets:
        # Only single expressions can be a chunk node (CodeEditor passes an
        # `ast.expr`). Multi-statement snippets belong to the candidate fixture.
        try:
            node_probe = ast.parse(code, mode="eval").body
        except SyntaxError:
            continue
        for qtv, qname in QT_NAMES.items():
            for aggressive in (0, 1):
                state = State(aggressive=aggressive)
                # transform_chunk deep-copies internally, but re-parse for safety.
                node = ast.parse(code, mode="eval").body
                result, changed = transform_chunk(node, state, qtv)
                out.append(
                    {
                        "code": code,
                        "quote_type": qname,
                        "aggressive": aggressive,
                        "changed": bool(changed),
                        "result": result,  # None when not changed
                        "counters": counters(state),
                    }
                )
        _ = node_probe
    return out


def gen_call_candidates():
    out = []
    for code in CANDIDATE_SNIPPETS:
        state = State()
        try:
            chunks = call_candidates(code, state)
        except SyntaxError:
            continue
        out.append(
            {
                "code": code,
                "count": state.call_candidates,
                "candidates": [ast_to_string(c.node) for c in chunks],
            }
        )
    return out


def main():
    fixtures = {
        "format_transform.json": gen_format_transform(),
        "call_candidates.json": gen_call_candidates(),
    }
    for name, data in fixtures.items():
        path = os.path.join(HERE, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        print(f"wrote {path}: {len(data)} entries")


if __name__ == "__main__":
    main()
