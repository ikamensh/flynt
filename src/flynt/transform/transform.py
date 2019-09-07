import astor
import ast
import copy
from typing import Tuple

from flynt.transform.node_transformer import fstringify_node
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

    converted = None
    changed = False

    try:
        tree = ast.parse(code)
        converted, changed = fstringify_node(copy.deepcopy(tree))
    except SyntaxError:
        pass
    except FlyntException:
        pass
    except Exception:
        pass

    if changed and converted:
        new_code = astor.to_source(converted)
        new_code = new_code.strip()
        new_code = set_quote_type(new_code, quote_type)
        new_code = new_code.replace("\n", "\\n")
        new_code = new_code.replace("\t", "\\t")

        try:
            ast.parse(new_code)
        except Exception:
            changed = False
            return code, changed
        else:
            return new_code, changed

    return code, changed
