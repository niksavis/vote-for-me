"""
Integration tests for API security, specifically session ownership and access control.
"""

import os
import sys

# Add the app directory to the path so we can import the Flask app
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import app


class TestAPISessionSecurity:
    """Test API security with different user contexts using Flask test client."""

    def test_new_user_sees_no_sessions(self):
        """Test that a new user without any sessions sees an empty list."""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess.clear()  # Ensure clean session

            response = client.get("/api/my-sessions")
            assert response.status_code == 200

            data = response.get_json()
            sessions = data.get("sessions", [])
            assert len(sessions) == 0, "New user should see 0 sessions"

    def test_user_with_specific_creator_id(self):
        """Test that a user with a specific creator_id only sees their sessions."""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["creator_id"] = "test_user_12345"

            response = client.get("/api/my-sessions")
            assert response.status_code == 200

            data = response.get_json()
            sessions = data.get("sessions", [])

            # Verify all returned sessions belong to this creator
            for session in sessions:
                creator_id = session.get("creator_id")
                if creator_id:
                    assert creator_id == "test_user_12345", (
                        f"Session {session['id']} has wrong creator_id: {creator_id}"
                    )

    def test_different_users_see_different_sessions(self):
        """Test that different users see different sets of sessions."""
        user1_id = "test_user_11111"
        user2_id = "test_user_22222"

        with app.test_client() as client:
            # User 1's sessions
            with client.session_transaction() as sess:
                sess["creator_id"] = user1_id

            response1 = client.get("/api/my-sessions")
            assert response1.status_code == 200
            data1 = response1.get_json()
            sessions1 = data1.get("sessions", [])
            session_ids1 = {s["id"] for s in sessions1}

            # User 2's sessions
            with client.session_transaction() as sess:
                sess["creator_id"] = user2_id

            response2 = client.get("/api/my-sessions")
            assert response2.status_code == 200
            data2 = response2.get_json()
            sessions2 = data2.get("sessions", [])
            session_ids2 = {s["id"] for s in sessions2}

            # Verify no overlap between different users' sessions
            common_sessions = session_ids1.intersection(session_ids2)
            assert len(common_sessions) == 0, (
                f"Users should not share sessions: {common_sessions}"
            )

    def test_admin_user_behavior(self):
        """Test admin user access to my-sessions."""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["authenticated"] = True

            response = client.get("/api/my-sessions")
            assert response.status_code == 200

            data = response.get_json()
            assert "sessions" in data, "Admin should get sessions key in response"

    def test_session_creator_ownership(self):
        """Test that sessions returned have proper creator_id ownership."""
        test_creator_id = "test_ownership_user"

        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess["creator_id"] = test_creator_id

            response = client.get("/api/my-sessions")
            assert response.status_code == 200

            data = response.get_json()
            sessions = data.get("sessions", [])

            # Every session should either have no creator_id or match our creator_id
            for session in sessions:
                creator_id = session.get("creator_id")
                if creator_id is not None:
                    assert creator_id == test_creator_id, (
                        f"Session {session['id']} creator_id mismatch: {creator_id}"
                    )

    def test_api_response_structure(self):
        """Test that the API returns the expected response structure."""
        with app.test_client() as client:
            response = client.get("/api/my-sessions")
            assert response.status_code == 200
            assert response.content_type == "application/json"

            data = response.get_json()
            assert isinstance(data, dict), "Response should be a JSON object"
            assert "sessions" in data, "Response should contain 'sessions' key"
            assert isinstance(data["sessions"], list), "Sessions should be a list"

            # Check session object structure if any sessions exist
            for session in data["sessions"]:
                required_fields = ["id", "title", "status"]
                for field in required_fields:
                    assert field in session, f"Session missing required field: {field}"
