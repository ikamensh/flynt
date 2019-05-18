import re
import black

class QuoteTypes:
    single = "'"
    double = '"'
    triple_single = "'''"
    triple_double = '"""'
    all = [triple_double, triple_single, single, double]

def get_quote_type(code: str):
    from fstringify import lexer

    chunk = list(lexer.get_chunks(code))[0]
    assert len(chunk) == 2
    token = chunk.tokens[0]

    return token.get_quote_type()

def remove_quotes(code: str):
    quote_type = get_quote_type(code)
    body = code[len(quote_type):-len(quote_type)]
    return body

def set_quote_type(code: str, quote_type: str):
    if code[0] == 'f':
        prefix, body = 'f', remove_quotes(code[1:])
    else:
        prefix, body = '', remove_quotes(code)
    return prefix + quote_type + body + quote_type


class Leaf:
    """Bare minimum implemention of black `Leaf`"""

    def __init__(self, value):
        self.value = value


def force_double_quote_fstring(code):
    """Use black's `normalize_string`_quotes`"""

    result = re.findall("\\b(f'[^']+')", code)

    if not result:
        return code

    org = result[0]

    if '"' in org or "\\" in org:
        return code

    leaf = Leaf(org)
    black.normalize_string_quotes(leaf)  # mutates the argument
    return code.replace(org, leaf.value)
