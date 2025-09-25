"""
Unit tests for utility functions and helper methods.
"""

import os
import sys
from unittest.mock import Mock

# Add the app directory to the path so we can import the Flask app
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import (
    app,
    generate_creator_id,
    get_current_creator_id,
    can_access_session,
    is_session_owner,
    can_modify_session,
)


class TestSecurityFunctions:
    """Test security and access control functions."""

    def test_generate_creator_id_format(self):
        """Test that generate_creator_id returns expected format."""
        with app.test_request_context():
            creator_id = generate_creator_id()

            assert isinstance(creator_id, str)
            assert len(creator_id) > 10  # Should be reasonably long
            assert creator_id.startswith("public_")  # Expected prefix

            # Should contain timestamp-like number at the end
            parts = creator_id.split("_")
            assert len(parts) >= 3
            assert parts[-1].isdigit()  # Last part should be numeric timestamp

    def test_generate_creator_id_uniqueness(self):
        """Test that generate_creator_id produces unique IDs."""
        with app.test_request_context():
            ids = [generate_creator_id() for _ in range(10)]
            unique_ids = set(ids)
            assert len(unique_ids) == len(ids), "Creator IDs should be unique"

    def test_get_current_creator_id_with_existing(self):
        """Test get_current_creator_id when creator_id exists in session."""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                test_id = "test_creator_12345"
                sess["creator_id"] = test_id

            with app.test_request_context():
                from flask import session

                session.update({"creator_id": test_id})
                result, is_admin = get_current_creator_id()
                assert result == test_id
                assert is_admin is False

    def test_get_current_creator_id_creates_new(self):
        """Test get_current_creator_id creates new ID when none exists."""
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess.clear()  # Ensure no existing creator_id

            with app.test_request_context():
                from flask import session

                session.clear()
                result, is_admin = get_current_creator_id()

                assert isinstance(result, str)
                assert result.startswith("public_")
                assert is_admin is False

    def test_can_access_session_owner(self):
        """Test can_access_session returns True for session owner."""
        session_obj = Mock()
        session_obj.creator_id = "test_creator_123"

        result = can_access_session(session_obj, creator_id="test_creator_123")
        assert result is True

    def test_can_access_session_admin(self):
        """Test can_access_session returns True for admin."""
        session_obj = Mock()
        session_obj.creator_id = "different_creator"

        result = can_access_session(
            session_obj, creator_id="test_creator", is_admin=True
        )
        assert result is True

    def test_can_access_session_denied(self):
        """Test can_access_session returns False for non-owner non-admin."""
        session_obj = Mock()
        session_obj.creator_id = "different_creator"

        result = can_access_session(
            session_obj, creator_id="test_creator", is_admin=False
        )
        assert result is False

    def test_can_access_session_no_creator_id(self):
        """Test can_access_session with session that has no creator_id."""
        session_obj = Mock()
        session_obj.creator_id = None

        # Should allow access when session has no creator_id
        result = can_access_session(session_obj, creator_id="test_creator")
        assert result is True

    def test_is_session_owner_true(self):
        """Test is_session_owner returns True for actual owner."""
        session_obj = Mock()
        session_obj.creator_id = "test_creator_123"

        result = is_session_owner(session_obj, creator_id="test_creator_123")
        assert result is True

    def test_is_session_owner_false(self):
        """Test is_session_owner returns False for non-owner."""
        session_obj = Mock()
        session_obj.creator_id = "different_creator"

        result = is_session_owner(session_obj, creator_id="test_creator")
        assert result is False

    def test_is_session_owner_admin_override(self):
        """Test is_session_owner returns True for admin even if not owner."""
        session_obj = Mock()
        session_obj.creator_id = "different_creator"

        result = is_session_owner(session_obj, creator_id="test_creator", is_admin=True)
        assert result is True

    def test_can_modify_session_delegates_to_is_session_owner(self):
        """Test that can_modify_session properly delegates to is_session_owner."""
        session_obj = Mock()
        session_obj.creator_id = "test_creator_123"

        # Should return True for owner
        result = can_modify_session(session_obj, creator_id="test_creator_123")
        assert result is True

        # Should return False for non-owner
        result = can_modify_session(session_obj, creator_id="different_creator")
        assert result is False

        # Should return True for admin
        result = can_modify_session(
            session_obj, creator_id="different_creator", is_admin=True
        )
        assert result is True
