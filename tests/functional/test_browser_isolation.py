"""
Functional tests for browser session isolation.
Tests that different browsers/sessions cannot see each other's voting sessions.
"""


class TestBrowserIsolation:
    """Test session isolation between different browser sessions."""

    def test_initial_empty_state(self, base_url, session_factory):
        """Test that all new sessions start with empty session lists."""
        browsers = [
            ("Browser 1", session_factory()),
            ("Browser 2", session_factory()),
            ("Browser 3", session_factory()),
        ]

        for name, browser in browsers:
            response = browser.get(f"{base_url}/api/my-sessions")
            assert response.status_code == 200

            data = response.json()
            sessions = data.get("sessions", [])
            assert len(sessions) == 0, f"{name} should start with 0 sessions"

    def test_session_creation_isolation(self, base_url, session_factory):
        """Test that sessions created in one browser are not visible in others."""
        browser1 = session_factory()
        browser2 = session_factory()
        browser3 = session_factory()

        # Create session in Browser 1
        create_response1 = browser1.post(
            f"{base_url}/api/sessions",
            json={
                "title": "Browser 1 Session",
                "votes_per_participant": 10,
                "anonymous": True,
            },
        )
        assert create_response1.status_code == 200
        session_data1 = create_response1.json()
        session_id1 = session_data1.get("session_id")
        assert session_id1 is not None

        # Create session in Browser 2
        create_response2 = browser2.post(
            f"{base_url}/api/sessions",
            json={
                "title": "Browser 2 Session",
                "votes_per_participant": 5,
                "anonymous": True,
            },
        )
        assert create_response2.status_code == 200
        session_data2 = create_response2.json()
        session_id2 = session_data2.get("session_id")
        assert session_id2 is not None

        # Verify session visibility isolation
        self._verify_session_isolation(
            base_url, browser1, browser2, browser3, session_id1, session_id2
        )

    def test_no_cross_contamination(self, base_url, session_factory):
        """Test that sessions from different browsers never appear together."""
        browser1 = session_factory()
        browser2 = session_factory()

        # Create multiple sessions in each browser
        browser1_sessions = []
        browser2_sessions = []

        for i in range(2):
            # Browser 1 session
            response1 = browser1.post(
                f"{base_url}/api/sessions",
                json={
                    "title": f"Browser 1 Session {i + 1}",
                    "votes_per_participant": 10,
                    "anonymous": True,
                },
            )
            assert response1.status_code == 200
            browser1_sessions.append(response1.json().get("session_id"))

            # Browser 2 session
            response2 = browser2.post(
                f"{base_url}/api/sessions",
                json={
                    "title": f"Browser 2 Session {i + 1}",
                    "votes_per_participant": 5,
                    "anonymous": True,
                },
            )
            assert response2.status_code == 200
            browser2_sessions.append(response2.json().get("session_id"))

        # Check Browser 1 sessions
        response1 = browser1.get(f"{base_url}/api/my-sessions")
        assert response1.status_code == 200
        data1 = response1.json()
        visible_sessions1 = [s["id"] for s in data1.get("sessions", [])]

        # Check Browser 2 sessions
        response2 = browser2.get(f"{base_url}/api/my-sessions")
        assert response2.status_code == 200
        data2 = response2.json()
        visible_sessions2 = [s["id"] for s in data2.get("sessions", [])]

        # Verify no cross-contamination
        browser1_set = set(visible_sessions1)
        browser2_set = set(visible_sessions2)
        common_sessions = browser1_set.intersection(browser2_set)

        assert len(common_sessions) == 0, (
            f"Found cross-contamination: {common_sessions}"
        )

        # Verify each browser sees only its own sessions
        assert set(browser1_sessions) == browser1_set
        assert set(browser2_sessions) == browser2_set

    def _verify_session_isolation(
        self, base_url, browser1, browser2, browser3, session_id1, session_id2
    ):
        """Helper method to verify proper session isolation."""
        browsers = [
            ("Browser 1", browser1, 1, [session_id1]),
            ("Browser 2", browser2, 1, [session_id2]),
            ("Browser 3", browser3, 0, []),
        ]

        for name, browser, expected_count, expected_ids in browsers:
            response = browser.get(f"{base_url}/api/my-sessions")
            assert response.status_code == 200

            data = response.json()
            sessions = data.get("sessions", [])
            visible_ids = [s["id"] for s in sessions]

            assert len(sessions) == expected_count, (
                f"{name} should see {expected_count} sessions, sees {len(sessions)}"
            )

            for expected_id in expected_ids:
                assert expected_id in visible_ids, (
                    f"{name} should see session {expected_id}"
                )
