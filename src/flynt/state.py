"""This module contains global state of flynt application instance."""

verbose = False
quiet = False
aggressive = False
dry_run = False

percent_candidates = 0
percent_transforms = 0

call_candidates = 0
call_transforms = 0

invalid_conversions = 0

concat_candidates = 0
concat_changes = 0

# Backup of the initial state to support the tests, which should start with a clean state each time.
# Note: this assumes that all state variables are immutable.
_initial_state = dict(globals())


def _reset():
    """
    Resets the state variables to the initial values seen above.
    """
    globals().update(**_initial_state)
