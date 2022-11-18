CASES = [
    ("'b'.join(['a', 'c'])", '"abc"'),
    ("'blah'.join([thing, (thing - 1)])", 'f"{thing}blah{thing - 1}"'),
    ("'blah'.join([blah.blah, blah.bleh])", 'f"{blah.blah}blah{blah.bleh}"'),
    ("''.join([a, b, 'c'])", 'f"{a}{b}c"'),
    ('" ".join([a, "World"])', 'f"{a} World"'),
    ('"".join(["Finally, ", a, " World"])', 'f"Finally, {a} World"'),
    ('"x".join(("1", "2", "3"))', '"1x2x3"'),  # all static
    ('"x".join({"4", \'5\', "yee"})', '"4x5xyee"'),  # all static
    ('"y".join([1, 2, 3])', 'f"{1}y{2}y{3}"'),
    ('"a".join([b])', 'f"{b}"'),
    ('a.join(["1", "2", "3"])', None),  # Not a static joiner
    ('"a".join(a)', None),  # Not a static joinee
    ('"a".join([a, a, *a])', None),  # Not a static length
    ('"a".join([c for c in a])', None),  # comprehension should not be transformed (not a static length)
]
