import tokenize
import io


class QuoteTypes:
    single = "'"
    double = '"'
    triple_single = "'''"
    triple_double = '"""'
    all = [triple_double, triple_single, single, double]


def get_quote_type(code: str):
    from flynt.lexer.py_token import PyToken

    line_token = tokenize.tokenize(io.BytesIO(code.encode("utf-8")).readline)
    next(line_token)
    token = PyToken(next(line_token))

    return token.get_quote_type()


def remove_quotes(code: str):
    quote_type = get_quote_type(code)
    body = code[len(quote_type) : -len(quote_type)]
    return body


def set_quote_type(code: str, quote_type: str):
    if code[0] == "f":
        prefix, body = "f", remove_quotes(code[1:])
    else:
        prefix, body = "", remove_quotes(code)
    if quote_type in (QuoteTypes.single, QuoteTypes.triple_double):
        if body[-2:] == '\\"':
            body = body[:-2] + '"'
    return prefix + quote_type + body + quote_type
