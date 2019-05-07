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
