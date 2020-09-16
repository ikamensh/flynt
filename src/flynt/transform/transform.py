import ast
import copy
import traceback
from typing import Tuple

import astor

from flynt import state
from flynt.exceptions import FlyntException, ConversionRefused
from flynt.format import QuoteTypes, set_quote_type
from flynt.transform.FstringifyTransformer import fstringify_node


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
    except (SyntaxError, FlyntException, Exception) as e:
        if state.verbose:
            if isinstance(e, ConversionRefused):
                print(f"Not converting code '{code}': {e}")
            else:
                print(f"Exception {e} during conversion of code '{code}'")
                traceback.print_exc()
        state.invalid_conversions += 1
        return code, False
    else:
        if changed:
            new_code = astor.to_source(converted)
            new_code = new_code.strip()
            if str_in_str and quote_type == QuoteTypes.single:
                quote_type = QuoteTypes.double
            new_code = set_quote_type(new_code, quote_type)
            new_code = new_code.replace("\n", "\\n")
            new_code = new_code.replace("\t", "\\t")
            try:
                ast.parse(new_code)
            except Exception as e:
                if state.verbose:
                    print(
                        f"Failed to parse transformed code '{new_code}' given original '{code}'"
                    )
                    print(e)
                    traceback.print_exc()
                state.invalid_conversions += 1
                return code, False
            else:
                return new_code, changed

        return code, False
