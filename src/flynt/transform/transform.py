import ast
import copy
import logging
from typing import Tuple

from flynt.exceptions import ConversionRefused
from flynt.state import State
from flynt.transform.FstringifyTransformer import fstringify_node
from flynt.utils.format import QuoteTypes
from flynt.utils.utils import fixup_transformed
from flynt.utils.utils import str_in_str as str_in_str_fn

log = logging.getLogger(__name__)


def transform_chunk(
    tree: ast.AST,
    state: State,
    quote_type: str = QuoteTypes.triple_double,
) -> Tuple[str, bool]:
    """Convert a block of code to an f-string
    Args:
        tree: The code to convert as AST.
        state: State object, for settings and statistics
        quote_type: the quote type to use for the transformed result

    Returns:
       Tuple: resulting code, boolean: was it changed?
    """
    try:
        converted, changed = fstringify_node(
            copy.deepcopy(tree),
            state=state,
        )
        str_in_str = str_in_str_fn(converted)
        if changed:
            if str_in_str and quote_type == QuoteTypes.single:
                quote_type = QuoteTypes.double
            new_code = fixup_transformed(converted, quote_type=quote_type)

    except ConversionRefused as cr:
        log.warning("Not converting code due to: %s", cr)
        state.invalid_conversions += 1
        return None, False  # type:ignore # ideally should return one optional str
    except Exception as exc:
        level = logging.DEBUG if isinstance(exc, AssertionError) else logging.ERROR
        log.log(level, "Exception during conversion of code", exc_info=exc)
        state.invalid_conversions += 1
        return None, False  # type:ignore # ideally should return one optional str
    else:
        if changed:
            try:
                ast.parse(new_code)
            except SyntaxError:
                log.error(
                    f"Failed to parse transformed code `{new_code}`",
                    exc_info=True,
                )
                state.invalid_conversions += 1
                return None, False  # type:ignore # should return one optional str
            else:
                return new_code, changed

        return None, False  # type:ignore # ideally should return one optional str
