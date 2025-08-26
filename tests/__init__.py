"""
CV Review Bot Test Suite.

This package contains comprehensive tests for all components of the
CV Review Bot application, including unit tests, integration tests,
and end-to-end tests.

Test Structure:
- test_core_models.py: Tests for domain models and business logic
- test_utils.py: Tests for utility functions and validators
- test_sqlite_adapter.py: Tests for SQLite storage adapter
- test_openrouter_adapter.py: Tests for OpenRouter LLM adapter
- test_bot_integration.py: Tests for Telegram bot integration
- conftest.py: Shared fixtures and test configuration

Test Markers:
- @pytest.mark.unit: Unit tests for individual components
- @pytest.mark.integration: Integration tests between components
- @pytest.mark.database: Tests requiring database setup
- @pytest.mark.external: Tests requiring external services
- @pytest.mark.slow: Tests that may take longer to run

Usage:
    Run all tests: pytest
    Run unit tests only: pytest -m unit
    Run with coverage: pytest --cov=src
    Run specific test file: pytest tests/test_core_models.py
"""