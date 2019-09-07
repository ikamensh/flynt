import astor
import ast
import copy
from typing import Tuple

from flynt.transform.FstringifyTransformer import fstringify_node
from flynt.exceptions import FlyntException
from flynt.format import set_quote_type, QuoteTypes


def transform_chunk(
    code: str, quote_type: str = QuoteTypes.triple_double
) -> Tuple[str, bool]:
    """Convert a block of code to an f-string

    Args:
        code: The code to convert.
        quote_type: the quote type to use for the transformed result

    Returns:
       Tuple: resulting code, boolean: was it changed?
    """

    try:
        tree = ast.parse(code)
        converted, changed, str_in_str = fstringify_node(copy.deepcopy(tree))
    except (SyntaxError, FlyntException, Exception):
        return code, False
    else:
        if changed:
            new_code = astor.to_source(converted)
            new_code = new_code.strip()
            new_code = set_quote_type(
                new_code, quote_type if not str_in_str else QuoteTypes.double
            )
            new_code = new_code.replace("\n", "\\n")
            new_code = new_code.replace("\t", "\\t")
            try:
                ast.parse(new_code)
            except Exception:
                return code, False
            else:
                return new_code, changed

        return code, False
