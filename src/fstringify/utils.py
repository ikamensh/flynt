import re
import token
import tokenize


MOD_KEY_PATTERN = re.compile("(%\([^)]+\)s)")
MOD_KEY_NAME_PATTERN = re.compile("%\(([^)]+)\)s")
INDENT_PATTERN = re.compile("^(\ +)")
VAR_KEY_PATTERN = re.compile("(%[sd])")


def skip_file(filename):
    """use tokenizer to make a fancier
        `"s%" not in contents`
    """
    # fn = io.BytesIO(fn.encode("utf-8")).readline
    with open(filename, "rb") as f:
        try:
            g = tokenize.tokenize(f.readline)
            for toknum, tokval, _, _, _ in g:
                if toknum == token.OP and tokval == "%":
                    return False
        except tokenize.TokenError:
            pass

        return True

def get_indent(line):
    indented = INDENT_PATTERN.match(line)
    if indented:
        return indented[0]

    return ""
