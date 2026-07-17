#!/usr/bin/env python
"""Generate golden fixtures for the Rust percent pipeline (task #5).

Kept separate from gen_fixtures.py so the percent port owns its own fixtures
without touching the shared generator. Run with the project venv:

    .venv/bin/python flynt-rust/tests/fixtures/gen_percent_fixtures.py

Writes `percent.json` next to this script:
  - "transform": for each (src, aggressive), the exact flynt outcome of
    `transform_binop` + `fixup_transformed` — one of:
      {"kind": "ok",      "result": <final source text>}
      {"kind": "refused", "message": <ConversionRefused text>}
      {"kind": "error"}   (ordinary exception: KeyError/FlyntException/ValueError)
  - "candidates": for each corpus source, the number of percent candidates
    `percent_candidates` discovers.
"""
import ast
import glob
import json
import os

from flynt.candidates.ast_percent_candidates import percent_candidates
from flynt.exceptions import ConversionRefused
from flynt.state import State
from flynt.transform.percent_transformer import transform_binop
from flynt.utils.utils import fixup_transformed

HERE = os.path.dirname(os.path.abspath(__file__))
FLYNT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "flynt"))
SAMPLE_DIRS = [
    os.path.join(FLYNT, "test", "integration", "samples_in"),
    os.path.join(FLYNT, "test", "integration", "expected_out"),
    os.path.join(FLYNT, "test", "integration", "samples_in_concat"),
    os.path.join(FLYNT, "test", "integration", "expected_out_concat"),
]

CURATED = [
    # single value / generic
    "'%s' % x",
    "'%s' % obj.attr",
    "'%s' % d['k']",
    "'%s' % f(y)",
    "'%s' % (a + b)",
    "'%s' % (a if c else b)",
    "'%s' % 'hi'",
    # tuples / lists
    "'%s and %s' % (a, b)",
    "'%s and %s' % [a, b]",
    "'%s %s %s' % (a, b, c)",
    "'%s %s' % (a,)",  # arity mismatch
    "'%s' % (a, b)",  # arity mismatch
    # %d / %i / %u
    "'%d' % x",
    "'%d' % int(x)",
    "'%d' % len(x)",
    "'%i' % x",
    "'%u' % x",
    "'%5d' % x",
    "'%d and %d' % (a, b)",
    # numeric types + prefix
    "'%03X' % x",
    "'%03x' % x",
    "'%.03f' % x",
    "'%f' % x",
    "'%e' % x",
    "'%E' % x",
    "'%g' % x",
    "'%G' % x",
    "'%c' % x",
    "'%o' % x",
    "'%.3x' % x",
    "'%+d' % int(x)",
    "'%5.2f' % x",
    # length modifiers (ignored)
    "'%ld' % int(x)",
    "'%hd' % int(x)",
    "'%lf' % x",
    # r / a / s alignment
    "'%r' % x",
    "'%a' % x",
    "'%s' % x",
    "'%-5s' % x",
    "'%5s' % x",
    "'%20r' % x",
    "'%20a' % x",
    "'%-10s and %s' % (a, b)",
    # literal percents / quirks
    "'100%% done %s' % x",
    "'%%d' % (x,)",
    "'%%s' % (x,)",
    "'a%%b%s' % x",
    "'%s%%' % x",
    # mapping — nonliteral RHS (subscript per placeholder)
    "'%(k)s' % d",
    "'val: %(k)s' % d",
    "'%(a)s %(b)d' % d",
    "'%(a)s %(a)s' % d",
    "'%(name)-10s' % d",
    "'%(k)03d' % d",
    "'%(k)z' % d",  # unknown modifier -> unpacking refusal
    "'%(a)s %s' % d",  # mixed mapping + positional
    # mapping — literal dict RHS
    "'%(k)s' % {'k': v}",
    "'%(a)s %(b)s' % {'a': x, 'b': y}",
    "'%(k)s %(k)s' % {'k': v}",  # reuse
    "'%(a)s' % {'a': x, 'b': y}",  # extra key (ok)
    "'%(a)s %(b)s' % {'a': x}",  # missing key
    # refusals via unsupported RHS
    "'%s' % {x}",  # set
    "'%s' % (i for i in xs)",  # generator
]

AGGRESSIVE_LEVELS = [0, 1, 2]


def sample_sources():
    for d in SAMPLE_DIRS:
        for path in sorted(glob.glob(os.path.join(d, "*.py"))):
            with open(path, encoding="utf-8") as fh:
                yield path, fh.read()


def percent_binop_sources():
    """Every `str % ...` BinOp appearing in the integration corpus, unparsed."""
    seen = set()
    for _path, src in sample_sources():
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.BinOp)
                and isinstance(node.op, ast.Mod)
                and isinstance(node.left, ast.Constant)
                and isinstance(node.left.value, str)
            ):
                try:
                    unparsed = ast.unparse(node)
                    ast.parse(unparsed, mode="eval")
                except Exception:
                    continue
                if unparsed not in seen:
                    seen.add(unparsed)
                    yield unparsed


def outcome(src, aggressive):
    # transform_binop mutates node.right for list/generic; re-parse each call.
    tree = ast.parse(src, mode="eval").body
    try:
        result = transform_binop(tree, aggressive=aggressive)
        out = fixup_transformed(result)
        return {"kind": "ok", "result": out}
    except ConversionRefused as e:
        return {"kind": "refused", "message": str(e)}
    except Exception:
        return {"kind": "error"}


def gen_transform():
    sources = list(CURATED)
    seen = set(sources)
    for s in percent_binop_sources():
        if s not in seen:
            seen.add(s)
            sources.append(s)

    out = []
    for src in sources:
        # skip anything that isn't a single top-level `%` expression
        try:
            node = ast.parse(src, mode="eval").body
        except SyntaxError:
            continue
        if not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod)):
            continue
        for aggressive in AGGRESSIVE_LEVELS:
            out.append(
                {"src": src, "aggressive": aggressive, **outcome(src, aggressive)}
            )
    return out


def gen_candidates():
    out = []
    # curated snippets (statements/expressions) + full corpus files
    curated_code = [
        "a = '%s\\n' % var",
        "print('{}'.format(x), '%d' % var)",
        "src_info = 'application \"%s\"' % obj.name",
        "['%s' % a, '%d' % b, '%r' % c]",
        "f(a % b, '%s' % c)",
        "x = (a % b) + ('%s' % c)",
        "'%s' % {x}",  # set RHS still a candidate
        "no_percent = 'plain'",
    ]
    for code in curated_code:
        n = len(percent_candidates(code, state=State()))
        out.append({"code": code, "count": n})
    for path, src in sample_sources():
        try:
            n = len(percent_candidates(src, state=State()))
        except Exception:
            continue
        out.append({"code": src, "count": n})
    return out


def main():
    data = {"transform": gen_transform(), "candidates": gen_candidates()}
    path = os.path.join(HERE, "percent.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    print(
        f"wrote {path}: {len(data['transform'])} transform, "
        f"{len(data['candidates'])} candidate entries"
    )


if __name__ == "__main__":
    main()
