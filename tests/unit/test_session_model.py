"""
Unit tests for the VotingSession class.
"""

import os
import sys
from unittest.mock import patch, mock_open

# Add the app directory to the path so we can import the Flask app
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import VotingSession


class TestVotingSession:
    """Test the VotingSession class functionality."""

    def test_voting_session_init_with_data(self):
        """Test VotingSession initialization with existing data."""
        session_data = {
            "id": "test-session-123",
            "title": "Test Session",
            "description": "Test Description",
            "creator_id": "test_creator",
            "status": "active",
            "settings": {
                "votes_per_participant": 5,
                "anonymous": True,
            },
        }

        session = VotingSession(session_data)

        assert session.id == "test-session-123"
        assert session.title == "Test Session"
        assert session.description == "Test Description"
        assert session.settings["votes_per_participant"] == 5
        assert session.settings["anonymous"] is True
        assert session.creator_id == "test_creator"
        assert session.status == "active"

    def test_voting_session_init_empty(self):
        """Test VotingSession initialization with no data."""
        session = VotingSession()

        assert hasattr(session, "id")
        assert hasattr(session, "title")
        assert hasattr(session, "description")
        assert hasattr(session, "settings")
        assert hasattr(session, "creator_id")
        assert hasattr(session, "status")
        assert hasattr(session, "created")
        assert session.settings["votes_per_participant"] == 10
        assert session.settings["anonymous"] is True

    def test_mark_completed(self):
        """Test marking a session as completed."""
        session = VotingSession({"status": "active"})
        session.mark_completed()

        assert session.status == "completed"

    def test_to_dict(self):
        """Test converting session to dictionary."""
        session_data = {
            "id": "test-session-456",
            "title": "Dict Test Session",
            "description": "Dict Description",
            "creator_id": "dict_creator",
            "status": "pending",
            "settings": {
                "votes_per_participant": 10,
                "anonymous": False,
            },
        }

        session = VotingSession(session_data)
        result_dict = session.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["id"] == "test-session-456"
        assert result_dict["title"] == "Dict Test Session"
        assert result_dict["description"] == "Dict Description"
        assert result_dict["settings"]["votes_per_participant"] == 10
        assert result_dict["settings"]["anonymous"] is False
        assert result_dict["creator_id"] == "dict_creator"
        assert result_dict["status"] == "pending"

    def test_get_file_path(self):
        """Test getting the file path for session data."""
        session_data = {"id": "test-session-789", "created": "2025-01-15T10:30:00Z"}

        session = VotingSession(session_data)
        file_path = session.get_file_path()

        assert hasattr(file_path, "name")  # Path object should have name attribute
        assert "test-session-789" in str(file_path)
        assert "2025-01-15" in str(file_path)
        assert str(file_path).endswith(".json")

    def test_get_key_file_path(self):
        """Test getting the key file path for session."""
        session_data = {"id": "test-session-key", "created": "2025-01-15T10:30:00Z"}

        session = VotingSession(session_data)
        key_path = session.get_key_file_path()

        assert hasattr(key_path, "name")  # Path object should have name attribute
        assert "test-session-key" in str(key_path)
        assert "2025-01-15" in str(key_path)
        assert str(key_path).endswith(".key")

    @patch("app.Path.replace")
    @patch("app.Path.mkdir")
    @patch("app.Path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("app.json.dump")
    @patch("app.Fernet.generate_key")
    def test_save_creates_directories_and_files(
        self,
        mock_generate_key,
        mock_json_dump,
        mock_file_open,
        mock_exists,
        mock_mkdir,
        mock_replace,
    ):
        """Test that save() creates necessary directories and files."""
        session_data = {
            "id": "test-save-session",
            "title": "Save Test",
            "created": "2025-01-15T10:30:00Z",
        }

        session = VotingSession(session_data)

        # Mock key file doesn't exist to trigger key generation
        mock_exists.return_value = False
        mock_generate_key.return_value = b"test_key"

        with patch.object(session, "_update_index_files"):
            session.save()

        # Verify directory creation is called
        mock_mkdir.assert_called()

        # Verify JSON is dumped
        mock_json_dump.assert_called()

        # Verify atomic file operations (replace) are called
        assert mock_replace.call_count >= 2  # Key file and JSON file

    @patch("app.Path.replace")
    @patch("app.Path.mkdir")
    @patch("app.Path.exists")
    @patch("builtins.open", new_callable=mock_open)
    @patch("app.json.dump")
    @patch("app.Fernet.generate_key")
    def test_save_creates_directory_if_not_exists(
        self,
        mock_generate_key,
        mock_json_dump,
        mock_file_open,
        mock_exists,
        mock_mkdir,
        mock_replace,
    ):
        """Test that save() creates directory when it doesn't exist."""
        session_data = {"id": "test-dir-session", "created": "2025-01-15T10:30:00Z"}

        session = VotingSession(session_data)

        # Mock key file doesn't exist to trigger key generation
        mock_exists.return_value = False
        mock_generate_key.return_value = b"test_key"

        with patch.object(session, "_update_index_files"):
            session.save()

        mock_mkdir.assert_called()

    def test_session_data_integrity(self):
        """Test that session data remains consistent through operations."""
        original_data = {
            "id": "integrity-test",
            "title": "Integrity Test Session",
            "description": "Test Description",
            "creator_id": "integrity_creator",
            "status": "active",
            "settings": {
                "votes_per_participant": 7,
                "anonymous": True,
            },
        }

        session = VotingSession(original_data)

        # Verify data integrity after to_dict()
        dict_data = session.to_dict()
        assert dict_data["id"] == original_data["id"]
        assert dict_data["title"] == original_data["title"]
        assert dict_data["description"] == original_data["description"]
        assert dict_data["settings"]["votes_per_participant"] == 7
        assert dict_data["settings"]["anonymous"] is True

        # Verify data integrity after status change
        session.mark_completed()
        assert session.status == "completed"

        # Other fields should remain unchanged
        assert session.id == original_data["id"]
        assert session.title == original_data["title"]
        assert session.description == original_data["description"]
