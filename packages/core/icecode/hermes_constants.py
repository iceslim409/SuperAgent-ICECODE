# Compatibility shim — use icecode_constants instead
from icecode.icecode_constants import *  # noqa: F401,F403
from icecode.icecode_constants import get_hermes_home as get_icecode_home  # noqa: F401
