"""Test isolation: never touch the real persisted settings file.

``copilot.server`` reads the settings file at import time, so this must run
before that import — pytest loads ``conftest.py`` first, which guarantees it.
"""

from __future__ import annotations

import os
import tempfile

os.environ["COPILOT_SETTINGS_FILE"] = os.path.join(
    tempfile.gettempdir(), "copilot-test-settings.json"
)
