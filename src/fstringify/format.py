import re

import black


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
