"""This module contains global state of flynt application instance."""

import dataclasses
from typing import Optional


@dataclasses.dataclass
class State:
    # -- Options
    quiet: bool = False
    aggressive: bool = False
    dry_run: bool = False
    stdout: bool = False
    multiline: bool = True
    len_limit: Optional[int] = None
    transform_percent: bool = True
    transform_format: bool = True
    transform_concat: bool = False
    transform_join: bool = False

    # -- Statistics
    percent_candidates: int = 0
    percent_transforms: int = 0

    call_candidates: int = 0
    call_transforms: int = 0

    invalid_conversions: int = 0

    concat_candidates: int = 0
    concat_changes: int = 0

    join_candidates: int = 0
    join_changes: int = 0

    def __post_init__(self):
        if not self.multiline:
            self.len_limit = 0
