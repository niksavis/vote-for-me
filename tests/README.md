# Vote For Me - Test Suite

This directory contains all automated tests for the Vote For Me application.

## Test Structure

```text
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # pytest fixtures and configuration
├── unit/                       # Unit tests
│   ├── __init__.py
│   ├── test_session_model.py   # VotingSession class tests
│   ├── test_session_manager.py # SessionManager class tests
│   └── test_security.py        # Security function tests
├── integration/                # Integration tests
│   ├── __init__.py
│   ├── test_api_endpoints.py   # API endpoint tests
│   └── test_my_sessions.py     # My Sessions functionality tests
└── functional/                 # End-to-end functional tests
    ├── __init__.py
    ├── test_browser_isolation.py  # Multi-browser session isolation
    └── test_voting_workflow.py    # Complete voting workflow tests
```

## Running Tests

### Using pytest (recommended)

```bash
# Install test dependencies
pip install pytest pytest-cov requests

# Run all tests
pytest

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/functional/

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/integration/test_my_sessions.py

# Run with verbose output
pytest -v
```

### Using Visual Studio Code

1. Install Python extension
2. Open Command Palette (Ctrl+Shift+P)
3. Select "Python: Configure Tests"
4. Choose "pytest"
5. Select "tests" directory
6. Tests will appear in the Test Explorer panel

### Using unittest (alternative)

```bash
# Discover and run all tests
python -m unittest discover tests/

# Run specific test module
python -m unittest tests.integration.test_my_sessions
```

## Test Categories

- **Unit Tests**: Test individual functions and classes in isolation
- **Integration Tests**: Test API endpoints and component interactions
- **Functional Tests**: Test complete user workflows and browser behavior

## Test Requirements

Tests require the application to be running on <http://localhost:5000>
