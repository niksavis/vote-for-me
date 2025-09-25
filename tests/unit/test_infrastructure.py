"""
Simple working tests to demonstrate the test infrastructure is functioning.
"""


class TestBasicInfrastructure:
    """Basic tests to verify test infrastructure is working."""

    def test_pytest_is_working(self):
        """Test that pytest is properly configured."""
        assert True

    def test_basic_math(self):
        """Test basic arithmetic to verify Python is working."""
        assert 2 + 2 == 4
        assert 10 / 5 == 2.0

    def test_string_operations(self):
        """Test string operations."""
        test_string = "Vote For Me"
        assert len(test_string) == 11
        assert test_string.lower() == "vote for me"
        assert "Vote" in test_string

    def test_list_operations(self):
        """Test list operations."""
        test_list = [1, 2, 3, 4, 5]
        assert len(test_list) == 5
        assert 3 in test_list
        assert test_list[0] == 1
        assert test_list[-1] == 5

    def test_dictionary_operations(self):
        """Test dictionary operations."""
        test_dict = {"session_id": "test-123", "title": "Test Session", "active": True}
        assert test_dict["session_id"] == "test-123"
        assert test_dict.get("title") == "Test Session"
        assert test_dict["active"] is True
        assert "status" not in test_dict
