from functools import partial

from flynt.candidates.ast_percent_candidates import percent_candidates
from flynt.code_editor import fstring_candidates
from flynt.utils.state import State

percent_candidates = partial(percent_candidates, state=State())
fstring_candidates = partial(fstring_candidates, state=State())


def test_str_newline():
    s_in = """a = '%s\\n' % var"""
    candidates = percent_candidates(s_in)
    assert len(list(candidates)) == 1


def test_triple():
    s_in = """print("{}".format(Bar + 1), '%d' % var, "{s}".format(s=foo))"""
    candidates = fstring_candidates(s_in)
    assert len(list(candidates)) == 3


def test_one_string():
    s = """"my string {}, but also {} and {}".format(var, f, cada_bra)"""
    chunks_gen = fstring_candidates(s)
    assert len(list(chunks_gen)) == 1

    candidates = fstring_candidates(s)
    chunk = next(iter(candidates))

    assert chunk.start_line == 0
    assert s[: chunk.end_idx] == s


def test_yields_parsable():
    code_in = """attrs = {'r': '{}'.format(row_idx)}"""
    candidates = fstring_candidates(code_in)
    chunk = next(iter(candidates))

    assert code_in[chunk.start_idx : chunk.end_idx] == "'{}'.format(row_idx)"


def test_percent_attribute():
    code_in = """src_info = 'application "%s"' % srcobj.import_name"""

    candidates = fstring_candidates(code_in)
    chunk = next(iter(candidates))

    expected = """'application "%s"' % srcobj.import_name"""
    assert code_in[chunk.start_idx : chunk.end_idx] == expected


def test_percent_call():
    code_in = """{"filename*": "UTF-8''%s" % url_quote(attachment_filename)}"""

    candidates = fstring_candidates(code_in)
    chunk = next(iter(candidates))

    expected = """"UTF-8''%s" % url_quote(attachment_filename)"""
    assert code_in[chunk.start_idx : chunk.end_idx] == expected


def test_two_strings():
    s = (
        'a = "my string {}, but also {} and {}".format(var, f, cada_bra)\n'
        + 'b = "my string {}, but also {} and {}".format(var, what, cada_bra)'
    )

    chunks_gen = fstring_candidates(s)
    assert len(list(chunks_gen)) == 2

    candidates = fstring_candidates(s)
    lines = s.split("\n")

    chunk = candidates[0]

    assert chunk.start_line == 0
    assert lines[0][: chunk.end_idx] == lines[0]

    chunk = candidates[1]

    assert chunk.start_line == 1
    assert lines[1][: chunk.end_idx] == lines[1]


indented = """
var = 5
if var % 3 == 0:
    a = "my string {}".format(var)""".strip()


def test_indented():

    candidates = fstring_candidates(indented)
    assert len(list(candidates)) == 1
    lines = indented.split("\n")

    candidates = fstring_candidates(indented)
    chunk = next(iter(candidates))

    assert chunk.start_line == 2
    assert lines[2][: chunk.end_idx] == lines[2]


def test_empty_line():
    code_empty_line = """
    def write_row(self, xf, row, row_idx):
    
        attrs = {'r': '{}'.format(row_idx)}""".strip()

    candidates = fstring_candidates(code_empty_line)
    lines = code_empty_line.split("\n")

    chunk = next(iter(candidates))

    assert chunk.start_line == 2
    assert lines[2][chunk.start_idx : chunk.end_idx] == "'{}'.format(row_idx)"


multiline_code = """
raise NoAppException(
            'Detected multiple Flask applications in module "{module}". Use '
            '"FLASK_APP={module}:name" to specify the correct '
            "one.".format(module=module.__name__)
        )
""".strip()


def test_multiline():
    candidates = fstring_candidates(multiline_code)
    assert len(list(candidates)) == 1


not_implicit_concat = """
html_logo = "_static/flask-logo-sidebar.png"
html_title = "Flask Documentation ({})".format(version)""".strip()


def test_not_implicit_concat():
    candidates = fstring_candidates(not_implicit_concat)
    assert len(list(candidates)) == 1


line_continuation = """
a = "Hello {}" \\
"world".format(',')""".strip()


def test_line_continuation():
    candidates = fstring_candidates(line_continuation)
    assert len(list(candidates)) == 1


tuple_in_list = """
latex_documents = [
    (master_doc, "Flask-{}.tex".format(version), html_title, author, "manual")
]""".strip()


def test_tuple_list():
    candidates = fstring_candidates(tuple_in_list)
    assert len(list(candidates)) == 1


def test_indexed_percent():
    code = 'return "Hello %s!" % flask.request.args[name]'
    candidates = fstring_candidates(code)
    chunk = next(iter(candidates))

    assert (
        code[chunk.start_idx : chunk.end_idx]
        == '"Hello %s!" % flask.request.args[name]'
    )


def test_tuple_percent():
    code = """print("%s %s " % (var+var, abc))"""
    candidates = fstring_candidates(code)
    assert len(list(candidates)) == 1
