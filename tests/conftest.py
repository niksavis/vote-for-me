"""
Pytest configuration and shared fixtures for the Vote For Me test suite.
"""

import pytest
import requests
import time
import uuid
from typing import Optional, Dict, Any


@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for the Flask application during testing."""
    return "http://localhost:5000"


@pytest.fixture(scope="session")
def app_running(base_url: str):
    """Verify that the Flask application is running before tests."""
    max_retries = 5
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            response = requests.get(base_url, timeout=5)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                pytest.skip(f"Flask application not running at {base_url}")

    return False


@pytest.fixture
def session_factory(base_url: str, app_running):
    """Factory for creating HTTP sessions for testing."""
    sessions = []

    def create_session():
        session = requests.Session()
        sessions.append(session)
        return session

    yield create_session

    # Cleanup
    for session in sessions:
        session.close()


@pytest.fixture
def unique_session_data():
    """Generate unique session data for testing."""
    session_id = str(uuid.uuid4())
    return {
        "session_id": session_id,
        "title": f"Test Session {session_id[:8]}",
        "presenter": f"Test Presenter {session_id[:8]}",
        "date": "2025-01-01",
    }


@pytest.fixture
def create_voting_session(base_url: str, session_factory, unique_session_data):
    """Create a voting session for testing."""

    def _create_session(custom_data: Optional[Dict[str, Any]] = None):
        session = session_factory()
        data = unique_session_data.copy()
        if custom_data:
            data.update(custom_data)

        # Get the main page to establish session
        session.get(base_url)

        # Create the voting session
        response = session.post(
            f"{base_url}/create-session", data=data, allow_redirects=False
        )

        return {"session": session, "data": data, "response": response}

    return _create_session


class TestSession:
    """Context manager for test sessions with automatic cleanup."""

    def __init__(self, session: requests.Session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()
