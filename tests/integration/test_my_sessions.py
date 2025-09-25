"""
Integration tests for the My Sessions API functionality.
"""

import pytest
import requests


class TestMySessionsAPI:
    """Test the /api/my-sessions endpoint functionality."""

    def test_my_sessions_empty_initially(self, base_url, session_factory):
        """Test that my-sessions is empty for new session."""
        session = session_factory()

        response = session.get(f"{base_url}/api/my-sessions")
        assert response.status_code == 200

        data = response.json()
        assert "sessions" in data
        assert len(data["sessions"]) == 0

    def test_create_and_list_session(self, base_url, session_factory):
        """Test creating a session and seeing it in my-sessions."""
        session = session_factory()

        # Create a new session
        create_response = session.post(
            f"{base_url}/api/sessions",
            json={
                "title": "Test Session for My Sessions",
                "votes_per_participant": 10,
                "anonymous": True,
            },
        )
        assert create_response.status_code == 200

        session_data = create_response.json()
        session_id = session_data.get("session_id")
        assert session_id is not None

        # Check that it appears in my-sessions
        response = session.get(f"{base_url}/api/my-sessions")
        assert response.status_code == 200

        data = response.json()
        sessions = data.get("sessions", [])
        assert len(sessions) == 1

        created_session = sessions[0]
        assert created_session["id"] == session_id
        assert created_session["title"] == "Test Session for My Sessions"
        assert created_session["status"] in ["draft", "active", "pending"]

    def test_no_duplicate_sessions(self, base_url, session_factory):
        """Test that sessions don't appear as duplicates."""
        session = session_factory()

        # Create multiple sessions
        session_titles = [
            "First Test Session",
            "Second Test Session",
            "Third Test Session",
        ]

        created_ids = []
        for title in session_titles:
            create_response = session.post(
                f"{base_url}/api/sessions",
                json={
                    "title": title,
                    "votes_per_participant": 5,
                    "anonymous": False,
                },
            )
            assert create_response.status_code == 200
            session_data = create_response.json()
            created_ids.append(session_data.get("session_id"))

        # Check my-sessions for duplicates
        response = session.get(f"{base_url}/api/my-sessions")
        assert response.status_code == 200

        data = response.json()
        sessions = data.get("sessions", [])

        # Verify all sessions are present
        assert len(sessions) == len(session_titles)

        # Check for duplicates
        session_ids = [s["id"] for s in sessions]
        unique_ids = set(session_ids)
        assert len(session_ids) == len(unique_ids), "Duplicate sessions detected"

        # Verify all created sessions are in the list
        for session_id in created_ids:
            assert session_id in session_ids

    def test_session_isolation_between_creators(self, base_url, session_factory):
        """Test that different creators only see their own sessions."""
        session1 = session_factory()
        session2 = session_factory()

        # Creator 1 creates a session
        create_response1 = session1.post(
            f"{base_url}/api/sessions",
            json={
                "title": "Creator 1 Session",
                "votes_per_participant": 5,
                "anonymous": True,
            },
        )
        assert create_response1.status_code == 200

        # Creator 2 creates a session
        create_response2 = session2.post(
            f"{base_url}/api/sessions",
            json={
                "title": "Creator 2 Session",
                "votes_per_participant": 3,
                "anonymous": False,
            },
        )
        assert create_response2.status_code == 200

        # Each creator should only see their own session
        response1 = session1.get(f"{base_url}/api/my-sessions")
        assert response1.status_code == 200
        data1 = response1.json()
        sessions1 = data1.get("sessions", [])
        assert len(sessions1) == 1
        assert sessions1[0]["title"] == "Creator 1 Session"

        response2 = session2.get(f"{base_url}/api/my-sessions")
        assert response2.status_code == 200
        data2 = response2.json()
        sessions2 = data2.get("sessions", [])
        assert len(sessions2) == 1
        assert sessions2[0]["title"] == "Creator 2 Session"
