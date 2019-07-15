import astor
import ast
import copy
from typing import Dict, Tuple

from flynt.transform.node_transformer import fstringify_node
from flynt.exceptions import FlyntException
from flynt.format import set_quote_type, QuoteTypes

def transform_chunk(code: str, quote_type: str = QuoteTypes.triple_double) -> Tuple[str, Dict]:
    """Convert a block of with a %-formatted string to an f-string

    Args:
        code (str): The code to convert.

    Returns:
       The code formatted with f-strings if possible else it's left unchanged.
    """

    converted = None
    meta = dict(changed=False, lineno=1, col_offset=-22, skip=True)

    try:
        tree = ast.parse(code)
        # from flynt.transform.util import pp_ast
        # pp_ast(tree)
        converted, meta = fstringify_node(copy.deepcopy(tree))
    except SyntaxError as e:
        meta["skip"] = code.rstrip().endswith(
            ":"
        ) or "cannot include a blackslash" in str(e)
    except FlyntException:
        meta["skip"] = False
    except Exception as e2:
        meta["skip"] = False

    if meta["changed"] and converted:
        new_code = astor.to_source(converted)
        new_code = new_code.strip()
        new_code = set_quote_type(new_code, quote_type)
        new_code = new_code.replace("\n", "\\n")
        new_code = new_code.replace("\t", "\\t")
        new_code = new_code.replace("{{{{", "{{")
        new_code = new_code.replace("}}}}", "}}")

        try:
            ast.parse(new_code)
        except Exception:
            meta["changed"] = False
            return code, meta
        else:
            return new_code, meta

    return code, meta
