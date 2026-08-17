"""ui — the learner-facing interface over the tutor core.

Strictly a view + one seam. It imports `tutor` read-only, writes state ONLY through
`gateway.dispatch` (no side doors, H1), and reaches the agents only via `runner.Runner`.
Nothing in `tutor/` knows this package exists.
"""
from .session import adopt_folder, adopt_zip, current_root, is_adopted, file_tree, SessionError
from .state import snapshot, who_is_active
from .runner import Runner, ScriptedRunner, SdkRunner, Event, default_script
from .server import App, handle, serve

__all__ = [
    "adopt_folder", "adopt_zip", "current_root", "is_adopted", "file_tree", "SessionError",
    "snapshot", "who_is_active",
    "Runner", "ScriptedRunner", "SdkRunner", "Event", "default_script",
    "App", "handle", "serve",
]
