"""Shared Streamlit mock for dashboard component tests."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# Set up the mock at module level so it is available when test modules are
# imported (before any fixtures run).  The connection module uses
# @st.cache_resource which must be a no-op during tests.
_st_mock = MagicMock()
_st_mock.cache_resource = lambda fn=None, **kwargs: (fn if fn is not None else lambda f: f)
_original = sys.modules.get("streamlit", None)
sys.modules["streamlit"] = _st_mock


@pytest.fixture(autouse=True)
def _mock_streamlit():
    """Ensure the streamlit mock is active for each test and restored after."""
    sys.modules["streamlit"] = _st_mock
    yield _st_mock
    if _original is not None:
        sys.modules["streamlit"] = _original
    else:
        sys.modules.pop("streamlit", None)
