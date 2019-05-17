from fstringify import lexer

def test_chunks_per_lines():
    code = "a=3\nb=4\nc=5\n"
    generator = lexer.get_chunks(code)
    assert len(list(generator)) == 3

def test_chunks_per_lines_no_newline():
    code = "a=3\nb=4\nc=5"
    generator = lexer.get_chunks(code)
    assert len(list(generator)) == 3

def test_chunks_per_lines_if():
    code = "a=3\nif a: b=4\nc=5"
    generator = lexer.get_chunks(code)
    assert len(list(generator)) == 3

def test_one_string():
    s = """"my string {}, but also {} and {}".format(var, f, cada_bra)"""
    chunks_gen = lexer.get_chunks(s)
    assert len(list(chunks_gen)) == 1

    generator = lexer.get_fstringify_lines(s)
    line, end_idx = next(generator)

    assert line == 0
    assert s[:end_idx] == s


def test_two_strings():
    s = 'a = "my string {}, but also {} and {}".format(var, f, cada_bra)\n' + \
    'b = "my string {}, but also {} and {}".format(var, what, cada_bra)'

    chunks_gen = lexer.get_chunks(s)
    assert len(list(chunks_gen)) == 2

    generator = lexer.get_fstringify_lines(s)
    lines = s.split('\n')

    line, end_idx = next(generator)

    assert line == 0
    assert lines[0][:end_idx] == lines[0]

    line, end_idx = next(generator)

    assert line == 1
    assert lines[1][:end_idx] == lines[1]




def test_indented():
    indented = """
    var = 5
    if var % 3 == 0:
        a = "my string {}".format(var)""".strip()

    chunks_gen = lexer.get_chunks(indented)
    assert len(list(chunks_gen)) == 3

    generator = lexer.get_fstringify_lines(indented)
    lines = indented.split('\n')

    line, end_idx = next(generator)

    assert line == 2
    assert lines[2][:end_idx] == lines[2]


def test_empty_line():
    code_empty_line = """
    def write_row(self, xf, row, row_idx):
    
        attrs = {'r': '{}'.format(row_idx)}""".strip()

    chunks_gen = lexer.get_chunks(code_empty_line)
    assert len(list(chunks_gen)) == 3

    generator = lexer.get_fstringify_lines(code_empty_line)
    lines = code_empty_line.split('\n')

    line, end_idx = next(generator)

    assert line == 2
    assert lines[2][:end_idx] == lines[2]


multiline_code = '''
raise NoAppException(
            'Detected multiple Flask applications in module "{module}". Use '
            '"FLASK_APP={module}:name" to specify the correct '
            "one.".format(module=module.__name__)
        )
'''.strip()

def test_multiline():
    generator = lexer.get_fstringify_lines(multiline_code)
    assert len(list(generator)) == 0


not_implicit_concat = '''
html_logo = "_static/flask-logo-sidebar.png"
html_title = "Flask Documentation ({})".format(version)'''.strip()

def test_not_implicit_concat():
    generator = lexer.get_fstringify_lines(not_implicit_concat)
    assert len(list(generator)) == 1


line_continuation = '''
a = "Hello {}" \\
"world".format(',')'''.strip()

def test_line_continuation():
    generator = lexer.get_fstringify_lines(line_continuation)
    assert len(list(generator)) == 0









