from __future__ import annotations

import pytest

from sighttalk_api.core.config import get_settings
from sighttalk_api.services.session_registry import get_session_registry


@pytest.fixture(autouse=True)
def clear_state() -> None:
    get_settings.cache_clear()
    get_session_registry().clear()
