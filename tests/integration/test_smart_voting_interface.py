"""
Test Smart Voting Interface Enhancement

Tests the status-aware voting interface, enhanced error handling,
and real-time updates for different session states.
"""

from app import session_manager


class TestSmartVotingInterface:
    """Test the smart voting interface enhancement features."""

    def test_session_timing_methods_basic(self):
        """Test session timing-related methods."""
        # Create session with timing
        session = session_manager.create_session(
            "Timed Session",
            "Test Description",
            votes_per_participant=5,
            anonymous=True,
        )

        # Test without timing constraints
        assert session.is_scheduled() is False
        assert session.can_vote_now() is False  # Draft session

        # Test status messages
        status_info = session.get_status_message()
        assert "type" in status_info
        assert "title" in status_info
        assert "message" in status_info

        # Draft session should show waiting status
        assert status_info["type"] == "waiting"

        # Test active session timing
        session.status = "active"
        session.mark_started()

        # Should be able to vote now
        assert session.can_vote_now() is True

        status_info = session.get_status_message()
        assert status_info["type"] == "active"

        # Test completed session
        session.status = "completed"
        session.mark_completed()

        assert session.can_vote_now() is False

        status_info = session.get_status_message()
        assert status_info["type"] == "ended"

    def test_enhanced_session_data_fields(self):
        """Test that sessions include all enhanced timing fields."""
        session = session_manager.create_session(
            "Enhanced Session",
            "Test Description",
            votes_per_participant=5,
            anonymous=True,
        )

        # Check default values
        session_dict = session.to_dict()

        # Enhanced timing fields should be present
        timing_fields = [
            "scheduled_start",
            "scheduled_end",
            "timezone",
            "auto_start",
            "auto_end",
            "notification_sent",
            "started_at",
            "completed_at",
        ]

        for field in timing_fields:
            assert field in session_dict, f"Missing timing field: {field}"

        # Check default values
        assert session_dict["scheduled_start"] is None
        assert session_dict["scheduled_end"] is None
        assert session_dict["timezone"] == "+00:00"
        assert session_dict["auto_start"] is False
        assert session_dict["auto_end"] is False
        assert session_dict["notification_sent"] is False
        assert session_dict["started_at"] is None
        assert session_dict["completed_at"] is None

        # Test mark_started and mark_completed
        session.mark_started()
        assert session.status == "active"
        assert session.started_at is not None

        session.mark_completed()
        assert session.status == "completed"
        assert session.completed_at is not None
