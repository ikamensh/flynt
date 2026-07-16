#!/usr/bin/env python
"""Generate golden fixtures for the Rust port's differential tests.

Run with the project venv:
    .venv/bin/python flynt-rust/tests/fixtures/gen_fixtures.py

Outputs JSON files next to this script. Each captures the *exact* behaviour of
flynt 1.0.6's Python helpers so the Rust port can be checked byte-for-byte.
"""
import ast
import glob
import io
import json
import os
import string
import tokenize

from flynt.utils.format import get_quote_type, get_string_prefix, set_quote_type, QuoteTypes
from flynt.utils.utils import (
    ast_to_string,
    contains_comment,
    fixup_transformed,
    str_in_str,
    unicode_escape_map,
    apply_unicode_escape_map,
)

HERE = os.path.dirname(os.path.abspath(__file__))
FLYNT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "flynt"))
SAMPLE_DIRS = [
    os.path.join(FLYNT, "test", "integration", "samples_in"),
    os.path.join(FLYNT, "test", "integration", "expected_out"),
    os.path.join(FLYNT, "test", "integration", "samples_in_concat"),
    os.path.join(FLYNT, "test", "integration", "expected_out_concat"),
]

QT_NAMES = {
    QuoteTypes.single: "single",
    QuoteTypes.double: "double",
    QuoteTypes.triple_single: "triple_single",
    QuoteTypes.triple_double: "triple_double",
}


def sample_sources():
    for d in SAMPLE_DIRS:
        for path in sorted(glob.glob(os.path.join(d, "*.py"))):
            with open(path, encoding="utf-8") as fh:
                yield path, fh.read()


def string_literal_tokens():
    """Every string-literal token text appearing across the sample corpus."""
    seen = set()
    for _path, src in sample_sources():
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
        except tokenize.TokenError:
            continue
        for tok in toks:
            if tok.type in (tokenize.STRING, getattr(tokenize, "FSTRING_START", -1)):
                txt = tok.string
                # only whole string tokens (STRING); skip fstring middle parts
                if tok.type == tokenize.STRING and txt not in seen:
                    seen.add(txt)
                    yield txt


def gen_quotes():
    out = []
    # from test_styles.py plus every literal in the corpus
    base = ["'abra'", '"bobro"', "'''abra'''", '"""bobro"""', '"alpha123"', '"""alpha123"""']
    literals = list(base)
    for txt in string_literal_tokens():
        literals.append(txt)
    seen = set()
    for code in literals:
        if code in seen:
            continue
        seen.add(code)
        try:
            qt = get_quote_type(code)
        except Exception:
            continue
        # flynt's regex `['"]{3}` can match three mixed quote chars in degenerate
        # short literals like '"' -> returns non-canonical token. Such literals are
        # never fed to get_quote_type by the real pipeline (only format/percent/
        # concat/join *candidate* leading strings are), so skip them here.
        if qt not in QT_NAMES:
            continue
        entry = {
            "code": code,
            "prefix": get_string_prefix(code),
            "quote_type": QT_NAMES[qt],
            "set": {},
        }
        for qtv, name in QT_NAMES.items():
            entry["set"][name] = set_quote_type(code, qtv)
        out.append(entry)
    return out


def expr_sources():
    """Canonical source of every expression node in the corpus, plus curated cases."""
    curated = [
        # conversions
        "f'{x!r}'", "f'{x!s}'", "f'{x!a}'",
        "f'{str(x)}'", "f'{repr(x)}'",
        # format specs
        "f'{x:>10}'", "f'{x:.03f}'", "f'{x:{width}}'", "f'{x:{width}.{prec}f}'",
        # nested quotes / string in string
        "f\"{d['a']}\"", "f'{a}' + f'{b}'",
        "f'{ {1, 2} }'",
        # ternaries inside replacement fields (exercise the paren-strip regex).
        # NOTE: a ternary WITH a format spec (e.g. f'{a if b else c:>5}') is a
        # documented ruff/ast.unparse divergence (ruff omits the defensive
        # parens CPython adds) and never appears in flynt's corpus, so it is not
        # included here.
        "f'{a if b else c}'",
        "f'{(a if b else c)}'",
        "f'prefix {x if y else z} suffix'",
        # lambda / yield-ish and other precedence cases
        "f'{a + b}'", "f'{a * b + c}'", "f'{-x}'",
        "f'{func(a, b, c)}'",
        "f'{obj.attr.method()}'",
        "f'{d[0]}'",
        # plain expressions
        "a % b", "'x' + y", "x.format(y)",
        "f'{x}{y}{z}'",
        "f'{ {\"k\": v} }'",
        # braces / literal escaping
        "f'{{literal}}'",
        "f'{x}%'",
        # unicode content
        "f'°{x}°'",
    ]
    seen = set()
    ordered = []

    def add(src):
        if src not in seen:
            seen.add(src)
            ordered.append(src)

    for src in curated:
        add(src)

    for _path, source in sample_sources():
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.expr):
                try:
                    src = ast.unparse(node)
                except Exception:
                    continue
                # keep only ones that re-parse standalone in eval mode
                try:
                    ast.parse(src, mode="eval")
                except SyntaxError:
                    continue
                add(src)
    return ordered


def gen_unparse():
    out = []
    for src in expr_sources():
        try:
            node = ast.parse(src, mode="eval").body
        except SyntaxError:
            continue
        try:
            expected = ast_to_string(node)
        except Exception:
            continue
        out.append({"src": src, "expected": expected})
    return out


def gen_str_in_str():
    out = []
    for src in expr_sources():
        try:
            node = ast.parse(src, mode="eval").body
        except SyntaxError:
            continue
        try:
            val = str_in_str(node)
        except Exception:
            continue
        out.append({"src": src, "result": val})
    return out


def gen_contains_comment():
    cases = [
        "x = 1",
        "x = 1  # trailing comment",
        "# leading comment",
        "'a string # with hash'",
        '"# not a comment"',
        "f'{x}  # inside fstring? no'",
        "a = [1, 2]  # list",
        "'%s' % x",
        "'{}'.format(y)",
        "'no comment here at all'",
    ]
    out = []
    for code in cases:
        try:
            res = contains_comment(code)
        except Exception:
            continue
        out.append({"code": code, "result": res})
    return out


def gen_escape():
    literals = [
        '"Feels like: {}\\u00B0F"',
        '"Feels like: {}\\u00B0F°"',
        '"plain"',
        '"tab\\tend"',
        '"\\x41\\x42"',
        '"octal \\101\\102"',
        '"mixed °\\u00B0 both"',
        "'single \\u00e9'",
        '"\\U0001F600 grin"',
    ]
    out = []
    for lit in literals:
        try:
            mapping = unicode_escape_map(lit)
        except Exception:
            continue
        # apply to the decoded body (simulate re-inserting escapes into unparsed text)
        try:
            decoded = ast.literal_eval(lit)
        except Exception:
            decoded = None
        applied = None
        if decoded is not None:
            # fresh copy of mapping because apply mutates it
            import copy
            applied = apply_unicode_escape_map(decoded, copy.deepcopy(mapping))
        out.append({
            "literal": lit,
            "map": mapping,  # dict[char -> list[str]]
            "decoded": decoded,
            "applied": applied,
        })
    return out


def format_strings():
    """Format-string templates: `.format()` call receivers plus a curated set."""
    curated = [
        "a{0}b", "{}", "x{name!r:>{w}}y", "{}.{}f", "literal only", "{:>5}",
        "pre{x}", "{{literal}}", "a}}b", "{x:{y}}", "{x:{y:{z}}}", "100%% {x}",
        "{}{}", "{d[a:b]}", "{0.name}", "{x!s}", "", "no fields", "{a}{b}{c}",
        "{:.2f}", "{name:{spec}}",
    ]
    seen = set()
    ordered = []

    def add(s):
        if s not in seen:
            seen.add(s)
            ordered.append(s)

    for s in curated:
        add(s)

    for _path, source in sample_sources():
        try:
            tree = ast.parse(source)
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
                add(node.func.value.value)
    return ordered


def gen_stdlib_parse():
    parse = string.Formatter().parse
    out = []
    for s in format_strings():
        try:
            fields = [list(t) for t in parse(s)]
        except Exception:
            continue
        out.append({"src": s, "fields": fields})
    return out


def gen_fixup():
    """fixup_transformed over every f-string in the corpus for each quote type.

    This is the function the transform pipelines call to produce final source
    text; it is where the outer delimiter is normalised via set_quote_type, so
    it is the byte-for-byte contract that actually governs golden output.
    """
    out = []
    for src in expr_sources():
        try:
            probe = ast.parse(src, mode="eval").body
        except SyntaxError:
            continue
        if not isinstance(probe, ast.JoinedStr):
            continue
        for qtv, name in QT_NAMES.items():
            try:
                # fixup_transformed mutates the tree (FstrInliner), so re-parse.
                node = ast.parse(src, mode="eval").body
                result = fixup_transformed(node, quote_type=qtv)
            except Exception:
                continue
            out.append({"src": src, "quote_type": name, "result": result})
        # default (quote_type=None) path
        try:
            node = ast.parse(src, mode="eval").body
            out.append({"src": src, "quote_type": None, "result": fixup_transformed(node)})
        except Exception:
            pass
    return out


def main():
    fixtures = {
        "quotes.json": gen_quotes(),
        "unparse.json": gen_unparse(),
        "str_in_str.json": gen_str_in_str(),
        "contains_comment.json": gen_contains_comment(),
        "escape.json": gen_escape(),
        "fixup.json": gen_fixup(),
        "stdlib_parse.json": gen_stdlib_parse(),
    }
    for name, data in fixtures.items():
        path = os.path.join(HERE, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        print(f"wrote {path}: {len(data)} entries")


if __name__ == "__main__":
    main()
