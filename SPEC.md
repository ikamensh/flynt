# Flynt 1.0.6 behavioral specification

This document specifies the observable behavior of the Python implementation in
`../flynt/src/flynt` and its tests. It is a porting specification, not a design
proposal. Unless a section is explicitly marked otherwise, reproduce the actual
behavior, including conservative refusals and source-spelling quirks. The golden
files under `../flynt/test/integration` are the byte-for-byte output authority.

`[QUIRK]` marks behavior that appears accidental, unsafe, or needlessly tied to
the Python implementation. The text after each marker states both what Flynt
actually does and what a clean implementation would normally do.

The reference package version is `1.0.6`, and its declared Python range is
3.9+. Any source regenerated from an AST inherits the spelling choices of
Python's `ast.unparse`; untouched source is copied exactly.

## 1. Pipeline overview

### 1.1 Whole-code pipeline

`api.fstringify_code(contents, state, filename="<code>")` does this:

1. Parse the original `contents` as a Python module. On `SyntaxError`, log
   `Can't parse {filename} as a python file.` and return `None`.
2. If either `state.transform_percent` or `state.transform_format` is true, run
   the percent/`.format` editor pass.
3. If `state.transform_concat` is true, run the concatenation editor pass on the
   output of step 2. Failure of this optional pass is logged and ignored.
4. If `state.transform_join` is true, run the static-join editor pass on the
   output of step 3. Failure of this optional pass is logged and ignored.
5. Build `FstringifyResult(n_changes, original_length, new_length, content)`.
   Lengths are Python `len(str)` character counts, not encoded byte counts.
6. If content is unchanged, return the result immediately. If it changed, parse
   the final result again and require the number of top-level module statements
   to be unchanged; a parse or statement-count failure returns `None` and does
   not write the file.

The transformation order is therefore:

```text
percent + .format  ->  optional concatenation  ->  optional static join
```

Each editor pass reparses its complete input and discovers fresh candidates.

`[QUIRK]` The final safety check compares only parseability and the count of
top-level statements. It does not compare semantics or the AST. A clean safety
check would compare a normalized AST while deliberately allowing the formatting
node changes.

### 1.2 One candidate

The normal percent/`.format` path for one candidate is:

```text
parse full file
  -> discover AstChunk candidates
  -> sort percent and .format chunks by (start_line, start_idx)
  -> CodeEditor copies source before the chunk
  -> transform_chunk(deepcopy(chunk.node), State, original quote type)
  -> FstringifyTransformer builds Constant / FormattedValue / JoinedStr nodes
  -> FstrInliner flattens eligible nested f-strings
  -> ast.unparse + ast_to_string postprocessing
  -> set_quote_type + newline/tab escaping
  -> unicode-escape restoration / raw-prefix restoration
  -> length and multiline acceptance
  -> splice converted text and continue copying original source
```

Concatenation and static-join passes use the same `CodeEditor`, but call
`transform_concat` and `transform_join` instead of `transform_chunk`.

Only the candidate span is regenerated. Everything outside accepted spans,
including spacing, comments, line endings, and the presence or absence of a
final newline, is preserved by source slicing.

### 1.3 Change count

The result change count is the number of candidate spans actually spliced by
`CodeEditor`, not the number of AST nodes rewritten inside a span. A transformed
outer `.format` call can recursively rewrite nested calls and still counts as
one change. A transform that succeeds internally but is rejected by the line
length rule counts as zero applied changes.

## 2. Candidate discovery

Every discovery function parses the entire code with `ast.parse`. Parse errors
propagate to its caller. Visitors produce candidates in AST source order. When a
visitor recognizes a node, it records that node and deliberately does not visit
its children; this makes the recognized node the outermost candidate of that
kind.

### 2.1 `AstChunk` coordinates

An `AstChunk` wraps one expression node and exposes:

| Property | Value |
|---|---|
| `start_line` | `node.lineno - 1` |
| `end_line` | `node.end_lineno - 1`; assert it is present |
| `start_idx` | `node.col_offset` |
| `end_idx` | `node.end_col_offset`; assert it is present |
| `n_lines` | `1 + end_line - start_line` |

Lines are zero-based in `AstChunk`. Both column offsets are zero-based UTF-8
**byte** offsets, matching CPython AST coordinates; `end_idx` is exclusive and
is relative to `end_line`, not to the beginning of the chunk. `CodeEditor`
converts each byte offset to a Unicode character index before slicing Python
strings. This translation is required for examples such as `°` and `ﭗ` before
or inside a candidate.

`AstChunk.__str__` unparses the node through `ast_to_string`; if the resulting
text merely starts with `(` and ends with `)`, it removes those two characters.
`quote_type` is declared but always raises `NotImplementedError`.

### 2.2 Percent candidates: `ast_percent_candidates`

A node is discovered iff all of these hold:

- it is `ast.BinOp`;
- its operator is `ast.Mod` (`%`);
- its left operand is `ast.Constant` whose value is a Python `str`.

The right operand is not checked during discovery. Thus `"%s" % {x}` is a
candidate even though the normal transformer does not support an `ast.Set` RHS.
The visitor records a matched `BinOp` and does not descend into either operand.

Explicitly rejected by discovery:

- modulo whose left side is a variable, call, f-string (`JoinedStr`), or bytes;
- every non-`%` operator;
- `%` nested under a matched outer literal-percent expression.

Discovery adds the number found to `state.percent_candidates`.

### 2.3 `.format` candidates: `ast_call_candidates`

A node is discovered iff all of these hold:

- it is `ast.Call`;
- `call.func` is `ast.Attribute`;
- the attribute name is exactly lowercase `format`;
- the attribute receiver is `ast.Constant(str)`.

Adjacent/implicit string literals are already folded by the parser into one
string constant, so they qualify. Whitespace around attribute access is
irrelevant at the AST level.

Explicitly rejected by discovery:

- `template.format(...)` where `template` is a name;
- `some_call().format(...)`;
- `f"...".format(...)`;
- `b"...".format(...)`;
- attributes other than exact `format`.

Argument count, `*args`, `**kwargs`, field validity, reuse, and unused arguments
are not checked here. A matched call is recorded without descending into its
receiver or arguments. Discovery adds the number found to
`state.call_candidates`.

### 2.4 String-concatenation candidates: `string_concat/candidates`

`is_string_concat(node)` is true when either:

- `node` is a string constant or an existing f-string; or
- `node` is `BinOp(Add)` and `is_string_concat(left) OR
  is_string_concat(right)`.

`ConcatHound` only records `BinOp` nodes, so a bare literal is never itself a
candidate. An addition tree is a candidate if any branch anywhere contains a
plain string or f-string literal. A matched outer addition is not descended
into.

Explicitly rejected:

- additions with no string/f-string literal anywhere;
- bytes-only additions;
- subtraction and all other operators;
- nested additions below an already matched addition.

Discovery adds the number found to `state.concat_candidates`.

`[QUIRK]` This is syntactic, not type-aware: `"x" + 1` is accepted and can be
changed from a runtime `TypeError` to `f"x{1}"`. A clean implementation would
preserve failing behavior or require evidence that nonliteral operands are
strings.

### 2.5 Static-join candidates: `static_join/candidates`

A call qualifies when `get_static_join_bits` returns `(joiner, elements)`:

1. `call.func` is an `Attribute` named exactly `join`.
2. Its receiver passes `is_str_literal`, meaning a plain string constant or a
   `JoinedStr` f-string.
3. `ast.literal_eval(receiver)` supplies the joiner string.
4. The call has exactly one positional argument.
5. That argument is an `ast.List`, `ast.Tuple`, or `ast.Set`.
6. None of its elements is `ast.Starred`.

Element types are otherwise unrestricted. The call's keyword arguments are not
examined.

Explicitly rejected:

- dynamic or bytes joiners;
- a nonliteral joinee, generator expression, or comprehension;
- zero or multiple positional arguments;
- a starred list/tuple/set element.

Discovery adds the number found to `state.join_candidates`.

`[QUIRK]` Any f-string receiver, even one containing only literal text, passes
`is_str_literal` and then makes `ast.literal_eval` raise instead of being cleanly
rejected. Empty containers are also discovered but `transform_join` later calls
`pop()` on an empty list.

`[QUIRK]` Sets are converted in source AST element order even though runtime set
iteration order is not that order. Numeric and other non-string elements are
also converted even though `str.join` would raise. Keywords are silently
dropped. A clean implementation would reject all three cases.

## 3. Percent transformation

### 3.1 Transformer eligibility and preflight skips

`FstringifyTransformer.is_percent_stringify` is narrower than candidate
discovery. In addition to literal-left `%`, the RHS must be one of:

- `Tuple`, `List`, or `Dict`; or
- `Name`, `Attribute`, `Constant`, `Subscript`, `Call`, `BinOp`, or `IfExp`.

Before calling `transform_binop`, `visit_BinOp` skips without an exception if:

- the decoded left format string contains either `{` or `}`; or
- any string constant anywhere under the RHS has a decoded value containing
  any newline, tab, carriage return, single quote, double quote, percent sign,
  or backslash. The literal checks are effectively
  `("\n", "\t", "\r", "'", '"', "%s", "%")`, plus `"\\"`; `%s` is
  redundant because `%` is also checked.

An eligible node increments `state.percent_candidates` again before these
preflight skips. A successful AST conversion increments
`state.percent_transforms` before editor length checks.

### 3.2 Accepted percent grammar

The implementation uses these exact regex components:

```text
FORMATS = "diouxXeEfFgGcrsa"
FORMAT_GROUP = "[hlL]?[diouxXeEfFgGcrsa]"
FORMAT_GROUP_MATCH = "[hlL]?([diouxXeEfFgGcrsa])"
PREFIX_GROUP = "[+-]?[0-9]*[.]?[0-9]*"

ANY_DICT = (?<!%)%\([^)]+?\)
DICT_PATTERN = (%\([^)]+\)[+-]?[0-9]*[.]?[0-9]*[hlL]?[diouxXeEfFgGcrsa])
SPLIT_DICT_PATTERN = %\(([^)]+)\)([+-]?[0-9]*[.]?[0-9]*)[hlL]?([diouxXeEfFgGcrsa])
VAR_KEY_PATTERN = %([+-]?[0-9]*[.]?[0-9]*)[hlL]?([diouxXeEfFgGcrsa])
```

The prefix supports at most one sign, digits, an optional literal dot, and more
digits. It does not support the space flag, `#`, `*`, or general mapping-key
syntax. Optional `h`, `l`, or `L` is accepted and discarded.

Literal `%%` is replaced with `%` in literal segments.

`[QUIRK]` `VAR_KEY_PATTERN` has no negative lookbehind, so a percent inside `%%`
can also be interpreted as a conversion during splitting. A clean parser would
tokenize percent formatting rather than combine these regexes.

### 3.3 Conversion table

After extracting `fmt_prefix` and the final conversion character, the mapping
is:

| Percent type | Generated f-string behavior |
|---|---|
| `s` | no conversion flag; preserve prefix subject to alignment rules below |
| `r` | `!r`; preserve prefix subject to conservative refusal |
| `a` | `!a`; preserve prefix subject to conservative refusal |
| `i`, `u` | translate to `d`, then use the `%d` safety/wrapping rules |
| `d` | remove the explicit `d` type and use the `%d` safety rules |
| `o`, `x`, `X` | keep the type; replace every `.` in the prefix with `0` |
| `e`, `E`, `f`, `F`, `g`, `G`, `c` | append the same type after the prefix |
| optional `h`, `l`, `L` | ignore it |

Although the internal integer-type string is `"dxXob"`, `b` is not accepted by
the input regex and is unreachable from normal source.

The `.`-to-`0` prefix rewrite happens before `i`/`u` are translated to `d`.
Therefore it applies to an original `d`, `o`, `x`, or `X`, but not to an
original `i` or `u`.

For `%s` with a nonempty prefix:

- a leading `-` means left alignment; remove `-` and emit the remaining prefix,
  e.g. `%-5s -> {value:5}`;
- with aggressive level at least 1 and no leading `-`, explicitly right-align by
  prepending `>`, e.g. `%5s -> {value:>5}`;
- otherwise raise `ConversionRefused` with exactly:

```text
Default text alignment has changed between percent fmt and fstrings. Proceeding would result in changed code behaviour.
```

For `%r` or `%a`, any nonempty prefix at aggressive level 0 raises the same
alignment refusal. At aggressive level 1+, the prefix is retained without an
added `>`.

For `%d`, `%i`, and `%u`:

- a direct `int(...)` or `len(...)` call is assumed to return an integer; the
  type character is simply removed at every aggressive level;
- at aggressive level 0, every other expression raises exactly:

```text
Skipping %d formatting - fstrings behave differently from % formatting.
```

- at aggressive level 1, wrap the value in `int(...)` and remove the type;
- at aggressive level 2+, do not wrap it and remove the type.

`[QUIRK]` Calls are recognized only by the bare names `int` and `len`, which may
be shadowed. A clean implementation cannot assume those names refer to builtins.

### 3.4 Tuple and list RHS

For a tuple RHS:

1. Find all `VAR_KEY_PATTERN` matches in the decoded format string.
2. Require `len(tuple.elts) == len(matches)`; otherwise raise:

   ```text
   This expression involves tuple unpacking.
   ```

3. Split the format string with the same regex.
4. Pair placeholders and tuple elements strictly left-to-right.
5. Turn literal blocks into string constants after `%% -> %`.
6. Turn each value into a formatted value using the table above.

A list RHS is mutated into an equivalent tuple AST and follows the same path.

For a supported non-tuple expression with no mapping placeholder, the RHS is
wrapped in a synthetic one-element tuple; consequently exactly one ordinary
placeholder is required.

`[QUIRK]` `"%s" % value` changes behavior when `value` is a one-element tuple:
old formatting unwraps it as the argument tuple, while the generated f-string
formats the tuple itself. The project README acknowledges this divergence.

### 3.5 Mapping RHS

If `DICT_PATTERN` finds at least one placeholder, generic RHS handling switches
to mapping mode.

First, the number of full `DICT_PATTERN` matches must equal the number of
`ANY_DICT` matches. A mismatch raises exactly:

```text
Some locations have unknown format modifiers.
```

Each placeholder supplies `(prefix, key, type)`. Empty keys would raise
`FlyntException("could not find dict key")`, although the regex normally
prevents an empty key.

For a literal `ast.Dict` RHS:

- literal-evaluate each non-`None` key, convert it with `str(...)`, and map it to
  the corresponding value expression;
- at aggressive level 0, remove a key from the map when used, so a repeated key
  causes a `KeyError` and the whole candidate is skipped;
- at aggressive level 1+, reuse is allowed.

For every nonliteral supported RHS, generate a fresh subscript per placeholder:
`rhs['key']`. Repeated keys are allowed even without aggressive mode.

Literal blocks again perform `%% -> %`. Extra keys in a literal dict are not an
error.

`[QUIRK]` Repeating a mapping expression such as `make_map()` in generated
subscripts reevaluates it once per placeholder, whereas percent formatting
evaluated it once. A clean implementation would bind once or refuse. Literal
dict values can likewise be reordered from dict construction order into format
field order.

### 3.6 Other refusal and error paths

Calling `transform_binop` directly with an unsupported RHS raises a
`ConversionRefused` whose dynamic text is:

```text
Unsupported `node.right` class: {Python type repr}
```

The normal `FstringifyTransformer` eligibility check usually prevents this
path. Formatting any expression whose unparsed spelling begins with `{` raises:

```text
values starting with '{' are better left not transformed.
```

Missing mapping keys, non-literal dict keys, and reused literal-dict keys are
ordinary exceptions, not `ConversionRefused`; `transform_chunk` still catches
them and skips the candidate.

## 4. `.format(...)` call transformation

### 4.1 Initial validation and argument map

`joined_string(call, aggressive=False)` requires a literal string receiver or
raises exactly:

```text
Only literal format strings are supported
```

It builds `var_map` as follows:

- each keyword is stored under `keyword.arg`;
- each positional argument is stored under integer keys `0, 1, ...`.

Before parsing fields, walk every positional and keyword value. For each string
constant, and for each bytes/bytearray constant decoded as Latin-1, refuse if
the value contains newline, tab, carriage return, or backslash, or if the entire
value is exactly `"` or exactly `'`. The exact refusal is:

```text
f-string expression part cannot include a backslash
```

`FstringifyTransformer` separately skips a call containing any positional
`ast.Starred` argument. There is no equally early `**kwargs` check.

### 4.2 Field parser and argument selection

Fields are parsed with Python `string.Formatter().parse`, preserving its errors
and its reduction of doubled braces.

For each `(raw, field_name, format_spec, conversion)`:

1. Add nonempty `raw` as a string constant.
2. If `field_name is None`, continue.
3. If `field_name` contains `[` anywhere, raise:

   ```text
   Skipping f-stringify of a fmt call with indexed name {field_name}
   ```

4. If it contains `.`, split at the first dot. The prefix selects the argument;
   the entire remainder becomes one `ast.Attribute.attr` suffix.
5. Select the base argument:
   - all digits: integer positional key and set `manual_field_ordering = True`;
   - empty: the next automatic positional key; assert manual ordering has not
     already been seen, then increment `seq_ctr`;
   - otherwise: exact string keyword key.
6. In non-aggressive mode, remove the selected key from `var_map`. Missing or
   repeated selection raises exactly:

   ```text
   A variable {identifier} is used multiple times - better not to replace it.
   ```

7. In aggressive mode, look up without removing, permitting reuse.
8. If an attribute suffix exists, wrap the selected expression in
   `ast.Attribute`.
9. Build the formatted value, including nested format fields.

Supported field examples include `{}`, `{0}`, `{name}`, `{x.y}`, `{0.y}`, and
the leading-attribute form `{.y}`. Argument expressions themselves may contain
arbitrary attribute or index access, so `"{}".format(a[0].x)` is supported.
Field-language indexing such as `{x[0]}` or `{0[key]}` is always rejected, as
pinpointed by `indexed_fmt_name.py`.

`[QUIRK]` A multi-component suffix such as `x.y.z` is stored as the single
attribute name `"y.z"`; `ast.unparse` happens to print it as a chain. A clean AST
would contain nested `Attribute` nodes.

### 4.3 Nested format specs

If an outer `format_spec` contains `{`, `_build_format_spec` parses it again with
`Formatter.parse` and builds a `JoinedStr` format spec:

- literal pieces become constants;
- numeric nested fields use integer keys;
- empty nested fields consume positional keys starting at current `seq_ctr`;
- named nested fields use exact string keys;
- each nested value is emitted with conversion `-1` and no nested format spec.

The helper returns the number of automatic positions consumed and the set of
used keys. The outer loop advances `seq_ctr`; non-aggressive mode removes used
nested keys from `var_map`.

Examples:

```text
"{:{}}".format(x, y)       -> f"{x:{y}}"
"{:{fill}}".format(x, fill=c) -> f"{x:{c}}"
"{} {:>{}}".format(a,b,c)  -> f"{a} {b:>{c}}"
"{0:{1}.{2}f}"...          -> f"{x:{w}.{p}f}"
```

Nested fields' own conversion and nested format strings are ignored.

### 4.4 Conversion flags, constants, and call simplification

The field conversion from `Formatter.parse` is converted to its character code
after removing an optional `!`; `None` becomes `-1`. Normal valid flags are
`!s`, `!r`, and `!a`. Invalid flags eventually fail during `ast.unparse` or the
post-transform parse and leave the candidate unchanged.

When there is no format spec and no explicit conversion, a direct one-argument
`str(x)` or `repr(x)` call with no keywords becomes `x!s` or `x!r`.

If the selected value is already an `ast.FormattedValue`, it is returned as-is.
If it is a plain string constant and there is no format spec, it is returned as
a literal segment rather than a formatted field. After all fields, if every
segment is a string constant, the result is one ordinary string constant, not
an f-string.

`[QUIRK]` The constant shortcut ignores an explicit conversion. For example, a
literal used with `!r` can lose the repr conversion. A clean implementation
would inline constants only after applying the requested conversion.

### 4.5 Reuse, unused values, and aggressive mode

After all fields, non-aggressive mode requires `var_map` to be empty. Otherwise
it raises:

```text
Some variables were never used: {var_map repr} - skipping conversion, it's a risk of bug.
```

Aggressive mode (`state.aggressive >= 1`) permits both reused and unused values.

`[QUIRK]` Reordering fields can reorder side effects even in non-aggressive
mode: `"{1}{0}".format(f(), g())` evaluates `f` then `g`, while the f-string
evaluates `g` then `f`. Aggressive reuse reevaluates an argument expression for
each field, and aggressive omission drops evaluation entirely. A clean port
would refuse effectful reorder/reuse/omission or introduce temporaries.

## 5. `FstringifyTransformer`, traversal, and inlining

### 5.1 Visitor traversal

`FstringifyTransformer` is run on a deep copy of the candidate AST.

`visit_Call`:

- if format transformation is enabled and the call matches `is_call_format`,
  increment the candidate counter, skip starred positional args, call
  `joined_string`, explicitly visit the resulting node, increment transformer
  count and `state.call_transforms`, and return the result;
- otherwise return the original call **without** `generic_visit`.

The explicit visit of the transformed result allows nested `.format` calls in
inserted expressions to be transformed, as in:

```text
"Hello {}".format(d["a{}".format(key)])
-> f"Hello {d[f'a{key}']}"
```

`visit_BinOp`:

- if percent transformation is enabled and `is_percent_stringify` matches,
  increment the candidate counter, run preflight checks, transform it, increment
  transformer count and `state.percent_transforms`, and return the result;
- otherwise return the original binop **without** `generic_visit`.

Unlike the call path, the generated percent result is not explicitly revisited.

Other node types use normal `NodeTransformer.generic_visit`.

`[QUIRK]` Returning unmatched `Call` and `BinOp` nodes without generic traversal
prunes their entire subtrees. Candidate discovery partly compensates by making
separate chunks, but mixed overlapping candidate kinds can still be problematic.
A clean visitor would traverse unmatched nodes while preventing double edits.

### 5.2 Existing f-strings and string-in-string behavior

Existing f-strings are not themselves percent/`.format` conversion candidates.
The discovery visitors may nevertheless descend into their expression parts and
find an eligible inner operation. The separate `FstringFinder` yields every
encountered `JoinedStr` as an `AstChunk` but does not descend under a found
`JoinedStr`; it is not part of the normal editing pipeline.

After transformation, `str_in_str` reports true when a plain string constant or
another `JoinedStr` occurs inside a `FormattedValue`. If this is true and the
source quote type was a single quote, `transform_chunk` changes the target quote
to double. It does not otherwise refuse merely because a string is embedded.
Backslashes and control characters in embedded strings are handled by the
earlier conservative preflight skips.

### 5.3 `FstrInliner`

For every `JoinedStr`, scan its values. If a value is:

- an `ast.FormattedValue`;
- whose `.value` is another `ast.JoinedStr`; and
- whose `.format_spec` is `None`;

replace that outer formatted value with all values of the inner joined string.
Then recursively generic-visit the modified node. This runs both in
`fstringify_node` and again in `fixup_transformed`.

`[QUIRK]` The inliner does not check the outer conversion flag, so it can discard
the semantics of a conversion applied to a nested f-string. A clean inliner
would require both no format spec and no conversion.

### 5.4 `transform_chunk` result and error behavior

Its direct-call signature defaults `quote_type` to triple double quote (`"""`).
`CodeEditor` normally overrides this with the source candidate's detected quote.

If the transformer made no conversion, return `(None, False)`. If changed:

1. choose double quotes instead of source single quotes when `str_in_str` is
   true;
2. call `fixup_transformed`;
3. parse the generated snippet;
4. return `(new_code, True)` only when parsing succeeds.

A `ConversionRefused` logs `Not converting code due to: {message}`, increments
`state.invalid_conversions`, and returns `(None, False)`. Any other exception
logs `Exception during conversion of code`, at DEBUG for `AssertionError` and
ERROR otherwise, increments the same counter, and skips. A generated syntax
error logs `Failed to parse transformed code `{new_code}``, increments the
counter, and skips.

Length rules are not part of this AST transformer. They are applied afterward
by `CodeEditor`; therefore transformation statistics can increment even when no
source edit is accepted.

### 5.5 Optional concatenation transformer

The concat transformer recursively flattens every `Add` binop into ordered
parts, visits those parts, and flattens existing `JoinedStr.values` into the
same segment list. Plain string constants remain literal segments; every other
part becomes a formatted value.

- If all final segments are string constants, return one concatenated
  `Constant(str)`.
- Otherwise return a `JoinedStr`.
- If any original string constant contains a decoded backslash and there is at
  least one expression, do not consolidate the outer node; generic-visit it so
  eligible inner concatenations can still change.
- Before consolidating, require every visited part to have f-string nesting
  depth at most 1. On violation, rebuild the `+` expression from visited parts.

`check_sns_depth` counts `JoinedStr` nesting and raises internally with
`String embedding too deep: {depth} > {maxdepth}`; its public result is boolean.

`transform_concat` considers itself changed if any nested or outer conversion
incremented its counter. Force double quotes when the transformed tree itself is
a `JoinedStr`/string constant, or when it is a single-expression module whose
expression is one. `ValueError` or `ConversionRefused` during final formatting
returns `("", False)`.

`[QUIRK]` Rebuilding an outer `+` after an inner edit can report changed and
unparse a larger expression even though the outer concatenation was refused.

### 5.6 Optional static-join transformer

For each accepted join:

1. Interleave the decoded joiner between source-order elements.
2. Keep string constants literal; wrap every other element as a formatted
   value.
3. If every interleaved item is a string constant, concatenate to one ordinary
   string constant.
4. Otherwise return a `JoinedStr`.
5. Always format the result with double quotes.

The transform counter increments before construction. There is no local
exception handling.

## 6. Formatting and utility behavior

### 6.1 Prefix and quote recognition

Quote constants are:

```text
single        = '
double        = "
triple_single = '''
triple_double = """
all           = [triple_double, triple_single, single, double]
```

`get_string_prefix(code)` consumes the longest leading run of characters in
`furbFURB`, without validating legal Python prefix combinations.

`get_quote_type(code)` applies this anchored regex:

```regex
[furbFURB]*(['"]{3}|['"])
```

It returns the quote token or raises exactly:

```text
Can't determine quote type of the string {code}.
```

`remove_quotes` removes the recognized prefix and opening/closing quote tokens
by length.

### 6.2 `set_quote_type`

Given unparsed string source and a target quote:

1. Detect its prefix.
2. Remember whether any `f`/`F` exists.
3. Preserve all non-f prefix characters in original order.
4. Strip quotes to obtain the body.
5. If target is single quote or triple double quote, and the body ends in
   `\"`, remove that final backslash only.
6. Else, if target is double quote, escape every `"` not immediately preceded
   by `\` using regex `(?<!\\)"`.
7. If target is single quote, escape every `'` not immediately preceded by `\`
   using regex `(?<!\\)\'`.
8. Return `other_prefix + ("f" if it originally had f else "") + quote + body
   + quote`.

Thus prefix `F` is normalized to lowercase `f` and placed after other retained
prefix characters.

`[QUIRK]` The double-quote branch uses Python object identity (`is`) instead of
string equality. One-character interning normally makes editor inputs work, but
a dynamically allocated equal string can skip escaping. A clean implementation
would compare values.

`[QUIRK]` The quote regexes only inspect one immediately preceding backslash and
do not reason about even/odd backslash runs or triple delimiter sequences.

### 6.3 `ast_to_string` and `fixup_transformed`

`ast_to_string(node)` is exactly:

1. `ast.unparse(node).rstrip()`; this removes all trailing whitespace from the
   regenerated span.
2. Only when `node` itself is `JoinedStr`, remove the redundant parentheses that
   `ast.unparse` puts around a simple ternary expression using:

   ```regex
   search:  \{\(([^{}]+?\sif\s[^{}]+?\selse\s[^{}]+?)\)\}
   replace: {\1}
   ```

`fixup_transformed(tree, quote_type=None)` then:

1. runs `FstrInliner`;
2. calls `ast_to_string`;
3. maps an `ast.unparse` `ValueError` containing `Unknown f-string conversion`
   to `ConversionRefused` with the same message (notably on Python <3.12);
4. if quote type is absent, default string constants and joined strings to
   double quote; also default to double when unparsed text begins with `f"""`,
   `'''`, or `"""` according to the source's slice checks;
5. apply `set_quote_type` when a quote was selected;
6. replace actual newline characters with the two characters `\n`;
7. replace actual tab characters with the two characters `\t`.

Carriage return is not explicitly replaced here.

The unparser's expression spelling is observable: spaces around operators,
parentheses, string quote choice inside expressions, and escape spelling all
come from the running Python version before the steps above. The Rust port must
match the checked-in golden spellings rather than a generic Rust pretty printer.

### 6.4 Formatted-value helper rules

`ast_formatted_value` also has these cross-transform rules:

- an already formatted value is returned unchanged;
- an expression whose unparsed text begins with `{` raises the exact refusal
  shown in section 3.6;
- bare `str(x)` and `repr(x)` are simplified to conversion flags only when
  there is no requested format spec or conversion;
- a nonempty ordinary format spec becomes a `JoinedStr` containing that literal
  text;
- a string constant with no format spec is returned as a constant segment.

`[QUIRK]` Returning an existing `FormattedValue` unchanged also discards any new
format spec or conversion requested by the caller. A clean implementation would
compose the formatting or refuse it explicitly.

### 6.5 Comment detection

`contains_comment(code)` tokenizes with
`tokenize.generate_tokens(io.StringIO(code).readline)` and returns true if any
token has type `tokenize.COMMENT`. A `#` inside a string is not a comment.
Tokenizer errors propagate.

### 6.6 Unicode and octal escape preservation

The recognized escape regex is exactly:

```regex
\\(?:u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|x[0-9a-fA-F]{2}|N\{[^}]+\}|[0-7]{1,3})
```

`unicode_escape_map(literal)`:

1. detects the opening quote and skips a leading `furbFURB` prefix;
2. defines the body by stripping that opening token and the same number of
   characters from the **end of the entire candidate string**;
3. finds recognized escapes in order;
4. decodes each with the `unicode_escape` codec;
5. maps each decoded character to a list of its original escape spellings in
   encounter order; undecodable escapes are silently ignored.

`apply_unicode_escape_map(code, mapping)` creates one character-class regex from
the mapping keys. For every matching decoded character in generated source, it
pops and substitutes the next saved spelling; after a list is exhausted, later
occurrences remain literal.

`[QUIRK]` The input to `unicode_escape_map` is the whole formatting expression,
not just its left string token. The closing slice therefore removes the end of
`.format(...)` or `% rhs`, and escapes in arguments may enter the map. Applying
by decoded character can also restore an escape at the wrong occurrence. A
clean implementation would retain escape spans from the original literal token.

If `ast.unparse` already emits an escape rather than the decoded character, the
map does not restore original case; this is why `\xA0` can become `\xa0`.

## 7. `CodeEditor`

### 7.1 Edit-loop invariants

Construction converts `len_limit=None` to `sys.maxsize`, splits source with
`code.split("\n")`, and also stores each logical line encoded as UTF-8.

The candidate factory must return nonoverlapping candidates ordered from top to
bottom and left to right. The combined percent/format factory explicitly sorts
on `(start_line, start_idx)`; concat and join visitors already produce source
order.

For each chunk:

1. copy source from the previous cursor up to chunk start;
2. inspect and possibly transform the chunk;
3. if accepted, append converted text and advance the source cursor to the
   exclusive chunk end;
4. if skipped, leave the cursor at chunk start, so the next copy operation or
   final `add_rest` restores the untouched chunk.

After candidates, append the rest of the file. `add_rest` appends synthetic
`\n` separators, `edit` joins all fragments, then removes exactly the final one
character with `[:-1]`. This preserves whether the original had a final newline,
including the empty-file case. It also preserves CRLF because splitting on `\n`
leaves `\r` at the end of each CRLF logical line.

Calling `edit()` twice asserts with exactly `Tried to use JT twice.`

`[QUIRK]` Nonoverlap is only documented, not checked. The independently found
percent and format candidate lists can overlap across kinds, and sorting alone
does not make such edits safe. A clean implementation would select a
nonoverlapping outermost interval set.

### 7.2 Chunk-level skips

Skip before transforming when any of these holds:

- `contains_comment(code_in_chunk)` is true;
- the first string prefix contains `b` or `B`;
- any physical source line intersecting the chunk matches either skip regex.

The exact skip regexes are:

```regex
#[ ]*noqa.*flynt
#\s*flynt:\s*skip
```

They are case-sensitive and are searched anywhere on each line. The first
allows only literal spaces immediately after `#`; the second allows general
regex whitespace. A trailing comment after the AST chunk end is not inside the
chunk and is preserved rather than causing `contains_comment`, but it can still
match a skip regex because the entire physical line is checked.

Prefix recognition for byte/raw skipping uses:

```regex
[furbFURB]*(['"]{3}|['"])
```

on `snippet.lstrip()`. Quote detection itself is attempted on the unstripped
snippet; failure defaults the target quote to `"` and disables the escape map.

### 7.3 Raw and byte prefixes

Byte-prefixed candidates are never transformed. A source prefix containing `u`
is not explicitly restored; AST unparsing normally drops it, as shown by legacy
unicode-string tests.

For a raw source candidate, after all other formatting:

1. replace every textual pair `\\` in the generated source with one `\`;
2. if the result does not begin with `r` or `R`, prepend lowercase `r`.

Thus an unparsed f-string normally becomes `rf"..."`.

`[QUIRK]` The blanket backslash collapse applies to the entire generated
expression, not just literal text. A clean implementation would preserve raw
literal spelling structurally.

### 7.4 Multiline and line-length acceptance

`contract_lines = chunk.n_lines - 1`.

For a single-line candidate (`contract_lines == 0`), `lines_fit` is always true;
the line-length limit is not checked at all.

For a multiline candidate whose source opening quote is triple single or triple
double:

1. split generated text on the two characters `\n`;
2. append source text after the candidate (`rest`) to the final generated line;
3. require every generated line length to be at most
   `len_limit - candidate_start_character_column`;
4. replace every textual `\n` in the generated result with a real newline before
   splicing, thereby retaining the triple-string's physical lines.

For every other multiline candidate, require:

```text
len(converted + rest) <= len_limit - candidate_start_character_column
```

An accepted non-triple multiline expression is contracted to one line. Failure
logs exactly this warning template and leaves source unchanged:

```text
Skipping conversion of {AstChunk string} due to line length limit. Pass -ll 999 to increase it. (999 is an example, as number of characters.)
```

`State(multiline=False)` forces `len_limit=0`, making all multiline candidates
fail while still allowing every single-line candidate. The default direct API
state has no limit; the CLI default is 88.

`[QUIRK]` Triple-string continuation lines all receive the same reduced budget
based on the first line's starting column, even though they may have different
indentation. A clean line-length check would use each physical line's actual
column.

### 7.5 Unicode escape restoration and acceptance order

If transformation reports changed, restore the unicode escape map only when it
is nonempty and the source was not raw. Then calculate line fit. Raw processing
happens only after fit succeeds. Consequently the line-length check sees escape-
restored but not raw-prefix-restored text.

### 7.6 Redundant-parenthesis removal

After accepting a replacement, remove one surrounding source parenthesis pair
only when:

- the immediately preceding emitted fragment ends in `(`;
- the next untouched source character on the candidate's end line is `)`;
- scanning backward before that `(`, skipping whitespace, reaches no
  disqualifying character before either beginning or one of `(=[+*`.

If the first non-whitespace character is not in `(=[+*`, retain the parentheses.
On removal, delete the previous fragment's final `(` and advance the source
cursor over `)`.

This is why assignment grouping such as `x = (format_expr)` can contract, while
`("/" + basename).rstrip(...)` retains parentheses needed for attribute access.

## 8. CLI, configuration, API, and state

### 8.1 CLI flags and initial defaults

The parser program is `flynt`, description is `flynt v.{__version__}`, and
standard `-h/--help` is enabled. Flags are:

| Flag(s) | argparse destination/action | Initial default |
|---|---|---|
| `-v`, `--verbose` | count; mutually exclusive with quiet | `0` |
| `-q`, `--quiet` | store true | `False` |
| `--no-multiline` | store true; mutually exclusive with line length | `False` |
| `-ll`, `--line-length` | integer | `88` |
| `-d`, `--dry-run` | store true; mutually exclusive with stdout | `False` |
| `--stdout` | store true | `False` |
| `-s`, `--string` | store true | `False` |
| `--no-tp`, `--no-transform-percent` | store false as `transform_percent` | `True` |
| `--no-tf`, `--no-transform-format` | store false as `transform_format` | `True` |
| `-tc`, `--transform-concats` | store true | `False` |
| `-tj`, `--transform-joins` | store true | `False` |
| `-f`, `--fail-on-change` | store true | `False` |
| `-a`, `--aggressive` | count | `0` |
| `-e`, `--exclude` | one or more strings (`nargs="+"`) | `None` |
| `-nb`, `--notebook` | store true | `False` |
| `--version` | store true | `False` |
| `--report` | store true | `False` |
| positional `src` | zero or more strings | `[]` |

`--stdout` with nonzero verbose is an argparse error:

```text
--stdout should not be used with -v/--verbose
```

`--version` prints `1.0.6` and returns 0 even without `src`. Otherwise missing
`src` prints `flynt: error: the following arguments are required: src`, prints
usage, and returns 1 rather than invoking `parser.error`.

On Python below 3.9, requested concat/join transformation raises an `Exception`
whose message includes `Transforming string concatenations is only possible...`
or `Transforming joins is only possible...` and the current `sys.version_info`.

Logging format is `%(message)s`. Initial level is DEBUG when verbose is nonzero,
otherwise CRITICAL. The `flynt` logger becomes INFO for one `-v` and DEBUG for
two or more.

### 8.2 CLI state mapping and modes

`state_from_args` maps fields directly, with these special cases:

- `multiline = not args.no_multiline`;
- `quiet = args.quiet or args.stdout`;
- CLI `line_length` becomes `State.len_limit`.

String mode joins all `src` tokens with one ASCII space, calls
`fstringify_code`, prints converted content or the unchanged input on failure,
and always returns 0. It does not load project configuration.

If `src` contains exact `-`, it must be the only source or argparse errors with
`Cannot use '-' with a list of other paths`. Stdin mode reads all stdin and
unconditionally removes `len(os.linesep)` characters from its end, transforms,
prints the result, and returns 0; transform failure returns 1.

`[QUIRK]` Stdin truncates the last character even when input has no final line
separator (and assumes the platform separator length). A clean implementation
would remove a separator only when present.

File mode prints `Running flynt v.1.0.6`, optionally followed by
`Using config file at {path}`, unless state is quiet. Verbose mode prints
`Using following options: {argparse Namespace repr}`. Dry-run mode always prints
`Running flynt in dry-run mode. No files will be changed.` even when `--quiet`
was passed.

### 8.3 `pyproject.toml` and user configuration

Project-root lookup:

1. resolve all source paths against cwd;
2. find their deepest common ancestor;
3. walk it and its parents upward;
4. at each level, prefer an existing `.git`, then a directory `.hg`, then a file
   `pyproject.toml`; stop at the first marker;
5. use `pyproject.toml` in that selected root if present;
6. otherwise try `~/.flynt.toml` on Windows or
   `${XDG_CONFIG_HOME:-~/.config}/flynt.toml` elsewhere.

A project `pyproject.toml` reads only `[tool.flynt]`. Every config key is
normalized with `key.replace("--", "").replace("-", "_")`.

For a path ending in `flynt.toml`, parsing first reads `[tool.flynt]`, then
updates that mapping with every top-level TOML key. The intended user file is
therefore a flat top-level mapping.

CLI/file-mode merge rules:

1. Parse CLI once and perform stdout/verbose, version, missing-source, and
   string/stdin branching before loading config.
2. Find and parse config from `args.src`.
3. Warn about keys absent from the first argparse namespace using:

   ```text
   Unknown config options: {set repr}. This might be a spelling problem. Supported options are: {sorted list repr}
   ```

4. Call `parser.set_defaults(**cfg)`.
5. Parse the original CLI argument list again. Explicit CLI arguments override
   config defaults.
6. Rebuild `State`.

`[QUIRK]` Validation and early modes are not rerun after config merging. Config
cannot supply a missing `src` or affect string/stdin mode, and it can introduce
combinations that the first parse would have rejected. Unknown defaults are
warned about but still added to the argparse namespace and otherwise ignored.

### 8.4 `State`

Option fields and direct-API defaults:

| Field | Default |
|---|---:|
| `quiet` | `False` |
| `aggressive` | `0` |
| `dry_run` | `False` |
| `stdout` | `False` |
| `multiline` | `True` |
| `len_limit` | `None` |
| `report` | `False` |
| `transform_percent` | `True` |
| `transform_format` | `True` |
| `transform_concat` | `False` |
| `transform_join` | `False` |
| `process_notebooks` | `False` |

Statistics fields all start at 0:

```text
percent_candidates, percent_transforms
call_candidates, call_transforms
invalid_conversions
concat_candidates, concat_changes
join_candidates, join_changes
```

`State.__post_init__` sets `len_limit = 0` whenever `multiline` is false,
overriding any supplied limit.

Counter mapping:

- percent/call discovery increments candidate counters once for every syntactic
  chunk, even when that transform kind is disabled but the shared pass runs;
- `FstringifyTransformer` increments the relevant candidate counter a second
  time for an enabled, transformer-eligible node, before preflight refusal;
- transform counters increment after AST construction, before editor length
  refusal and final file safety checks;
- `invalid_conversions` counts exceptions and invalid generated snippets in
  `transform_chunk`, not comments, skip directives, line-length refusals,
  whole-file parse failures, concat errors, or join errors;
- concat/join candidate counters come from discovery, while `concat_changes`
  and `join_changes` are increased by the number of editor spans actually
  accepted by the optional API stages.

`[QUIRK]` Candidate denominators are commonly double-counted, and transform
numerators can include edits later rejected by `CodeEditor`. A clean report
would count each attempted and each applied candidate exactly once.

### 8.5 File resolution and exclusions

Built-in blacklist strings are exactly:

```text
.tox
venv
site-packages
.eggs
```

For each requested path:

- convert it to an absolute path;
- if absent, print `` `{original}` not found `` and `sys.exit(1)`;
- recursively walk directories with `os.walk`, accepting `.py` and, when
  enabled, `.ipynb` filenames;
- accept a direct file only with those same suffix rules;
- normalize `\` to `/` in both paths and exclusions;
- retain a file iff every blacklist/user-exclusion string is **not a substring**
  of its normalized absolute path.

Traversal and filenames are not sorted, excluded directories are still walked,
duplicates are retained, `.pyi` and `.py2` are ignored by public resolution.

The exclusion API expects a collection of strings and applies
`set(excluded_files_or_paths)`. `[QUIRK]` Passing one bare string therefore makes
each character a separate exclusion substring; a clean API would treat a string
as one path pattern or reject the type.

`[QUIRK]` Exclusions are raw substrings, so a parent directory whose name
contains `venv` excludes all descendants. A clean implementation would use path
components or explicit glob semantics and prune excluded directories.

### 8.6 Normal files, encodings, and output modes

`encoding_by_bom` reads four bytes and checks, in order:

1. UTF-8 BOM -> `("utf-8-sig", BOM_UTF8)`;
2. UTF-32 little/big BOM -> `("utf-32", matched_bom)`;
3. UTF-16 little/big BOM -> `("utf-16", matched_bom)`;
4. otherwise `("utf-8", None)`.

Files are read with that encoding and `newline=""`; decode failure logs
`Exception while reading {filename}` and returns `None`. On accepted changes,
normal mode writes binary, first writes the saved BOM if any, then writes
`new_code.encode(encoding)`.

`[QUIRK]` The BOM-aware encoders themselves emit a BOM, so explicitly writing
the saved BOM can produce a double BOM. The existing BOM test only checks that a
change result exists, not exact output bytes. A clean implementation would emit
exactly one original BOM.

Mode precedence for a valid result is:

1. if dry-run and there are changes, print `difflib.unified_diff` joined with
   `\n`, using `fromfile=filename` and the default empty `tofile`;
2. else if stdout, `print(new_code)` even with no changes;
3. else if there are changes, overwrite the file;
4. otherwise do nothing.

`print` adds its own newline, so stdout can add a blank line after content that
already ends in a newline.

### 8.7 Notebook handling

An `.ipynb` file returns `None` unless `state.process_notebooks` is true. When
enabled:

1. load UTF-8 JSON; any error logs `Exception while reading {filename}` and
   returns `None`;
2. normalize the original JSON as
   `json.dumps(nb, ensure_ascii=False, indent=1)`;
3. iterate `nb.get("cells", [])` in order;
4. process only cells whose `cell_type == "code"`;
5. join `cell.get("source", [])`, transform it with a filename suffix `[index]`,
   and, if content differs, store `result.content.splitlines(keepends=True)`;
6. dump the changed notebook with the same JSON options and no trailing newline.

The same dry-run/stdout/write precedence applies to the normalized JSON.
Notebook result lengths count the normalized dumps, not original file bytes.
Markdown and already-f-string code cells remain semantically untouched, but the
whole JSON file is formatting-normalized when written.

### 8.8 API return values and safety

`FstringifyResult` is a frozen record with fields in this order:

```text
n_changes: int
original_length: int
new_length: int
content: str
```

`fstringify_files` returns the number of files with nonzero changes. A failed
file is logged as `fstringifying {path}...failed`; successful statuses are
`modified` and `no change`.

`fstringify(files_or_paths, state, fail_on_changes=False, exclusions=None)`
returns 0 by default even when files fail. With `fail_on_changes=True`, it
returns the changed-file count, which may be greater than 1.

The final whole-code diagnostics are exactly:

```text
Skipping fstrings transform of file {filename} due to {exception message or class name}.
Faulty result during conversion on {filename} - skipping.
Faulty result during conversion on {filename}: statement count has changed, which is not intended - skipping.
```

Both concat and join optional-stage exceptions use the same, slightly wrong log
message:

```text
Transforming concatenation of literal strings failed
```

### 8.9 Summary and detailed report strings

When not quiet and `report` is false:

```text
Modified {changed_files} of {found_files} files in {seconds:.2f}s
```

or, with zero changed files:

```text
No changes made to {found_files} file{s when found_files != 1} in {seconds:.2f}s
```

The detailed report starts and ends exactly as follows (the first two shown
lines each have a leading blank line):

```text

Flynt run has finished. Stats:

Execution time:                            {seconds:.3f}s
Files checked:                             {found_files}
Files modified:                            {changed_files}
...

_-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_._-_.
```

The `...` section exists only when at least one file changed:

```text
Character count reduction:                 {original-new} ({ratio:.2%})

Per expression type:
Old style (`%`) expressions attempted:     {percent_transforms}/{percent_candidates} ({fraction:.1%})
`.format(...)` calls attempted:            {call_transforms}/{call_candidates} ({fraction:.1%})
String concatenations attempted:           {concat_changes}/{concat_candidates} ({fraction:.1%})
Static string joins attempted:             {join_changes}/{join_candidates} ({fraction:.1%})
F-string expressions created:              {total_applied_changes}
```

For a zero candidate denominator, replace the corresponding line with exactly:

```text
No old style (`%`) expressions attempted.
No `.format(...)` calls attempted.
No concatenations attempted.
No static string joins attempted.
```

If `invalid_conversions > 0`, append:

```text
Out of all attempted transforms, {invalid_conversions} resulted in errors.
To find out specific error messages, use --verbose flag.
```

The character reduction line's embedded newline plus `print` creates the blank
line before `Per expression type:`. Per-type details and invalid-conversion
details are omitted entirely when no file changed.

## 9. Integration edge-case catalog

This catalog has one row for every file in `samples_in` and
`samples_in_concat`. “Unchanged” means the default golden output is identical to
input. The ordinary Python-file golden suite excludes `bom.py`, `class.py`,
`escaped_newline.py`, and `multiline_limit.py`; their actual status is stated
below. The `expected_out_single_line` variants for multiline fixtures are exact
copies of input because `multiline=False` forces `len_limit=0`.

### 9.1 `samples_in`

| File | Behavior pinned down |
|---|---|
| `CantAffordActiveException.py` | Converts a `.format` call at EOF while preserving the absence of a final newline. |
| `all_named.py` | Resolves all named fields to keyword value expressions and removes the call. |
| `bom.py` | API-only fixture proving a UTF-8-BOM file can be read and reports a change; it has no golden output and does not test exact BOM bytes. |
| `class.py` | `[QUIRK]` Excluded legacy fixture: checked-in expected text also removes `(object)`, but the current surgical editor only changes the class attribute string and retains `class Mysterios(object)`. Do not treat the unrelated class rewrite as required behavior. |
| `def_empty_line.py` | Preserves blank lines/indentation and no final newline around an inner dictionary value edit. |
| `dict_func.py` | Handles named arguments, a datetime format spec, and whitespace-heavy call arguments. |
| `digit_ordering.py` | Converts explicit positional field `{0:,}` and retains comma grouping. |
| `double_conv.py` | Converts three independent candidates on one line: expression `.format`, `%f`, and named `.format`. |
| `escaped_dq.py` | Preserves escaped double quotes in an outer double-quoted f-string. |
| `escaped_newline.py` | `[QUIRK]` Intentional xfail for issue #83: the desired checked-in output keeps backslash-newline spelling, but actual conversion loses those continuation escapes and changes triple-string layout; it is not a passing golden requirement. |
| `first_string.py` | Converts two separate `.format` calls in source order. |
| `hard_percent.py` | Converts `%03X`, `%f`, and `%.03f`, but leaves `%20r` and `%i` unchanged at aggressive level 0. |
| `implicit_concat.py` | Python folds adjacent literals before `.format`; accepted conversion contracts a backslash-continued expression to one line. |
| `implicit_concat_comment.py` | Unchanged because a tokenized comment occurs inside the candidate span. |
| `implicit_concat_named1.py` | Unchanged because the comment inside an implicitly concatenated named/positional format span vetoes conversion. |
| `implicit_concat_named2.py` | Unchanged for the same in-span comment rule, including repeated named use. |
| `indexed_fmt_name.py` | Unchanged because field syntax containing `[` (here `x[0]`, `x[1]`) is explicitly refused. |
| `indexed_percent.py` | Converts a single `%s` whose RHS is a nested subscript expression. |
| `insert_constant_str.py` | Folds a literal `.format("text")` argument directly into a multiline triple-quoted ordinary string; no f prefix remains. |
| `issue104.py` | Escape spelling is normalized by `ast.unparse`: octal `\033` becomes lowercase hex `\x1b` in both format styles. |
| `issue192.py` | Converts safe conditional `%s` expressions but refuses `.format` calls whose inserted string expressions contain backslashes/newlines. |
| `issue55.py` | Pins `ast.unparse` escape normalization from `\xA0` to `\xa0`. |
| `literal_string.py` | Inlines string constants, retains non-string constants as fields, escapes quotes, and collapses all-constant calls to ordinary strings. |
| `long.py` | Makes one local edit in a large real-world file without reformatting unrelated source. |
| `multiline.py` | Contracts an implicit-literal, multiline `.format` expression to one line when unlimited by the direct API; unchanged in single-line mode. |
| `multiline_1.py` | Contracts a parenthesized percent expression split around the `%` operator; unchanged in single-line mode. |
| `multiline_2.py` | Contracts multiline `.format` arguments and preserves the trailing `# Ok` comment outside the chunk; unchanged in single-line mode. |
| `multiline_3.py` | Unchanged because a comment token occurs inside the multiline call. |
| `multiline_dict.py` | Converts mapping-style percent formatting inside a triple string while preserving real internal newlines; unchanged in single-line mode. |
| `multiline_issue102.py` | Converts implicitly concatenated percent text and removes redundant outer grouping; unchanged in single-line mode. |
| `multiline_keep.py` | Adds `f` to a triple-quoted configuration string and retains all physical lines/comments inside the string; unchanged in single-line mode. |
| `multiline_limit.py` | Excluded from ordinary unlimited-state goldens; with CLI limit 88 its would-be one-line output is rejected, while an unlimited direct state converts it. The separate concat test leaves it unchanged. |
| `multiline_twice.py` | Unchanged because a named argument is referenced twice and non-aggressive mode refuses reuse. |
| `multiple.py` | Converts multiple independent `.format` lines without disturbing declarations. |
| `named_inverse.py` | Resolves named fields independently of keyword argument order. |
| `no_fstring_1.py` | Unchanged module with no candidate; also pins preservation without a final newline. |
| `no_fstring_2.py` | Unchanged module with an ordinary source comment and no candidate. |
| `octal_escape.py` | Unchanged by default because static joins are opt-in; join-specific tests separately pin octal escape preservation. |
| `percent_dict.py` | Converts a literal mapping RHS with `%f` and `%s` fields to direct value expressions. |
| `percent_numerics.py` | Preserves `f/e/g` type characters across a five-element tuple and spacing-normalizes expressions only inside the replacement. |
| `percent_op.py` | Converts a non-atomic binary RHS and preserves operator precedence as `{d ** 2}`. |
| `percent_strings.py` | Maps `%r`, `%s`, `%a` to `!r`, no flag, and `!a`. |
| `py2.py2` | API-only invalid-Python-3 fixture: direct `_fstringify_file` returns `None` and leaves bytes unchanged; public path resolution ignores `.py2`. |
| `quotes_issue107.py` | A multiline tuple containing single-quoted subscripts forces a double-quoted f-string and contracts to one line; unchanged in single-line mode. |
| `raw_string.py` | Preserves a raw prefix and produces `rf"..."` while collapsing unparser-added backslash doubling. |
| `regression_flask.py` | Converts percent formatting in a call argument without touching the surrounding docstring or keyword argument. |
| `simple.ipynb` | Notebook mode transforms only the one eligible code cell; markdown, existing f-string, and plain code cells remain logically unchanged. |
| `simple.py` | Baseline automatic `.format` conversion. |
| `simple_comment.py` | Preserves comments before and after a single-line candidate; a non-skip trailing comment does not veto. |
| `simple_docstring.py` | Leaves a module docstring untouched and edits a later assignment only. |
| `simple_format.py` | Preserves `.2f` in a basic format-spec conversion and no final newline. |
| `simple_format_double_brace.py` | `Formatter.parse` reduces doubled braces and f-string unparsing redoubles them to produce literal `{}`. |
| `simple_indent.py` | Preserves block indentation while replacing one span. |
| `simple_percent.py` | Baseline single-value `%s` conversion. |
| `simple_percent_comment.py` | Preserves a trailing ordinary comment after a percent candidate. |
| `simple_start.py` | Handles a replacement field at the beginning of the literal. |
| `simple_str_newline.py` | Distinguishes decoded newline from literal backslash-`n` and preserves the corresponding `\n` versus `\\n` source spelling. |
| `simple_str_return.py` | Same distinction for carriage-return escapes (`\r` versus `\\r`). |
| `simple_str_tab.py` | Same distinction for tab escapes (`\t` versus `\\t`). |
| `slash_quotes.py` | Preserves escaped double quotes, escaped newline spelling, and unrelated comments. |
| `some_named.py` | Mixes automatic positional fields with a named field, consuming each argument once. |
| `static_string_join.py` | Unchanged by default, proving static-join conversion requires explicit enablement. |
| `str_literal.py` | Inlines a literal string into a formatted field with alignment while contracting a multiline call; unchanged in single-line mode. |
| `string_in_string.py` | Converts safe quote-containing join expressions, switches outer single quotes to double, and refuses embedded strings containing backslash escapes. `[PYTHON-VERSION]` The original test explicitly skips this file on Python >=3.12 because it considers unparse behavior version-dependent, although the checked-in output has also been reproduced under Python 3.13. |
| `tuple_in_list.py` | Edits a `.format` call nested inside a tuple inside a list without altering container layout. |
| `two_liner.py` | Contracts short and very long implicit-literal calls under unlimited direct state; both remain input-identical in single-line mode. |
| `unicode_degree.py` | Converts correctly when multibyte UTF-8 characters affect AST byte offsets; subscript quotes are normalized inside the replacement. |
| `unicode_escape.py` | Preserves a literal double-backslash unicode escape sequence while converting the surrounding call. |

### 9.2 `samples_in_concat`

These goldens first run the normal percent/`.format` pass and then the concat
pass.

| File | Behavior pinned down |
|---|---|
| `backslash.py` | Contracts an explicitly backslash-continued addition and preserves shebang/blank lines/no final newline. |
| `cr_lf_concat.py` | Flattens repeated variable and literal pieces without interpreting the variables' runtime CR/LF contents. |
| `index.py` | Formats a subscript operand and preserves an ordinary trailing comment. |
| `literals_only.py` | Folds plain plus raw string literals to one ordinary double-quoted constant with escaped backslash. |
| `longer_line.py` | Single-line concat conversion ignores the state's line-length limit, so a line longer than 88 still changes. |
| `mixed_format.py` | Normal pass converts inner `.format` and `%f`; concat pass flattens the resulting f-strings, literals, and variable into one f-string. |
| `multiple.py` | Converts two separate addition trees, including literal-variable-literal order. |
| `newline_char.py` | Converts an expression plus decoded newline literal and preserves surrounding call spacing exactly. |
| `no_parens.py` | Converts literal-plus-call in a return expression without introducing parentheses. |
| `parens.py` | Retains source parentheses because the resulting f-string is the receiver of `.rstrip`. |
| `parens_multiline.py` | Removes redundant assignment parentheses while contracting a multiline addition. |
| `regex_sub.py` | Leaves a concat containing a decoded backslash in a regex argument unchanged, while earlier percent conversions of literal operands become constant-only f-strings. |

## 10. Porting order and conformance boundary

An engineer can implement and validate in this order without reading Python:

1. AST coordinates, candidate visitors, and source-preserving `CodeEditor`.
2. Expression/string unparse compatibility and quote/escape utilities.
3. `.format` fields without nested specs, then nested specs and conversions.
4. Percent tuple/generic cases, mapping cases, then aggressive levels.
5. Transformer traversal, inlining, and final parse/safety behavior.
6. Optional concat and join passes.
7. API file/notebook modes and statistics.
8. CLI/configuration/reporting.

For golden-file conformance, compare complete UTF-8 file contents, including
quote characters, escape case, CR/LF bytes, indentation, trailing spaces, and
final-newline presence. Do not normalize either side. Treat the exclusions and
xfail called out in section 9 according to the original test suite rather than
as ordinary passing golden files.
