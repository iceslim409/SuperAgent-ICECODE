# Compatibility shim — hermes_cli is now icecode_cli.hermes_cli
# This allows 'from icecode_cli.hermes_cli.X import Y' to work
import sys
import os

# Add cli package to path so hermes_cli can be found there
_cli_pkg = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'cli')
if _cli_pkg not in sys.path:
    sys.path.insert(0, _cli_pkg)

try:
    from icecode_cli.hermes_cli import *  # noqa: F401,F403
except ImportError:
    pass
