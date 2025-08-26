"""
Pytest configuration and shared fixtures for CV Review Bot tests.

This module provides common fixtures and configuration for all tests,
including database setup, mock objects, and test data.
"""

import os
import sys
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.models import (
    Submission, Report, AnalysisRequest, AnalysisResult, 
    RepositoryContent, FileInfo, Role, SubmissionStatus, RecommendationLevel
)
from database import Base


# Test Configuration
TEST_DATABASE_URL = "sqlite:///:memory:"
TEST_REPO_URL = "https://github.com/test/test-repo"
TEST_USER_ID = "123456789"
TEST_USERNAME = "test_user"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_db_engine():
    """Create a test database engine with in-memory SQLite."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine):
    """Create a test database session."""
    SessionFactory = sessionmaker(bind=test_db_engine)
    session = SessionFactory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def temp_directory():
    """Create a temporary directory for test files."""
    temp_dir = tempfile.mkdtemp(prefix="cv_review_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_env_vars():
    """Mock environment variables for testing."""
    env_vars = {
        'BOT_TOKEN': 'test_bot_token',
        'OPENROUTER_KEY': 'test_openrouter_key',
        'DATABASE_PATH': ':memory:',
        'MAX_REPO_SIZE_MB': '50',
        'ANALYSIS_TIMEOUT': '300',
        'MAX_CONCURRENT': '2',
        'PRIMARY_MODEL': 'test/primary-model',
        'FALLBACK_MODEL': 'test/fallback-model',
        'TEMPERATURE': '0.1',
        'MANAGER_IDS': '123456789,987654321'
    }
    
    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


# Domain Model Fixtures

@pytest.fixture
def sample_file_info() -> FileInfo:
    """Create a sample FileInfo object."""
    return FileInfo(
        path="src/main.py",
        content="def main():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    main()",
        priority="critical",
        tokens=25,
        language="python"
    )


@pytest.fixture
def sample_repository_content(sample_file_info) -> RepositoryContent:
    """Create a sample RepositoryContent object."""
    return RepositoryContent(
        url=TEST_REPO_URL,
        files=[sample_file_info],
        total_tokens=25,
        structure="src/\n  main.py",
        metadata={"branch": "main", "commit": "abc123"}
    )


@pytest.fixture
def sample_analysis_request(sample_repository_content) -> AnalysisRequest:
    """Create a sample AnalysisRequest object."""
    return AnalysisRequest(
        repository_content=sample_repository_content,
        role=Role.BACKEND,
        task_requirements="Create a simple backend service with proper architecture.",
        github_url=TEST_REPO_URL,
        submission_id=1
    )


@pytest.fixture
def sample_analysis_result() -> AnalysisResult:
    """Create a sample AnalysisResult object."""
    return AnalysisResult(
        requirements_met={
            "architectural_pattern": True,
            "repository_pattern": False,
            "service_layer": True,
            "redis_implementation": False,
            "database_implementation": True
        },
        scores={
            "task_completion": 75.0,
            "code_quality": 80.0,
            "architecture": 70.0,
            "testing": 60.0,
            "critical_issues_penalty": 10.0
        },
        recommendation=RecommendationLevel.ACCEPT,
        confidence=0.85,
        strengths=[
            "Clean code structure",
            "Good separation of concerns",
            "Proper error handling"
        ],
        weaknesses=[
            "Missing repository pattern",
            "Limited test coverage",
            "No Redis integration"
        ],
        detailed_feedback="The code shows good understanding of backend principles...",
        suggestions=[
            "Implement repository pattern",
            "Add more comprehensive tests",
            "Integrate Redis for caching"
        ],
        hiring_decision={"decision": "HIRE", "primary_reason": "Good technical competency"},
        penalty_breakdown={
            "issues_found": [
                {"issue": "Minor security concern", "severity": "low", "penalty": 10}
            ],
            "total_penalty": 10
        }
    )


@pytest.fixture
def sample_submission() -> Submission:
    """Create a sample Submission object."""
    return Submission(
        id=1,
        telegram_user_id=TEST_USER_ID,
        telegram_username=TEST_USERNAME,
        github_url=TEST_REPO_URL,
        role=Role.BACKEND,
        status=SubmissionStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_report(sample_analysis_result) -> Report:
    """Create a sample Report object."""
    return Report(
        id=1,
        submission_id=1,
        analysis_result=sample_analysis_result,
        model_used="test/model",
        tokens_used=1000,
        analysis_duration=30.5,
        created_at=datetime.now(timezone.utc)
    )


# Mock External Services

@pytest.fixture
def mock_github_api():
    """Mock GitHub API responses."""
    mock = MagicMock()
    mock.get_repo.return_value = MagicMock(
        name="test-repo",
        full_name="test/test-repo",
        clone_url="https://github.com/test/test-repo.git",
        default_branch="main",
        size=1024,  # KB
        language="Python"
    )
    mock.get_contents.return_value = [
        MagicMock(name="README.md", type="file", size=500),
        MagicMock(name="src", type="dir"),
        MagicMock(name="main.py", type="file", size=1500, path="src/main.py")
    ]
    return mock


@pytest.fixture
def mock_openrouter_response():
    """Mock OpenRouter API response."""
    return {
        "choices": [{
            "message": {
                "content": """{
                    "requirements_met": {
                        "architectural_pattern": true,
                        "repository_pattern": false,
                        "service_layer": true,
                        "redis_implementation": false,
                        "database_implementation": true
                    },
                    "scores": {
                        "task_completion": 75,
                        "code_quality": 80,
                        "architecture": 70,
                        "testing": 60,
                        "critical_issues_penalty": 10
                    },
                    "recommendation": "yes",
                    "confidence": 85,
                    "strengths": [
                        "Clean code structure",
                        "Good separation of concerns",
                        "Proper error handling"
                    ],
                    "weaknesses": [
                        "Missing repository pattern",
                        "Limited test coverage",
                        "No Redis integration"
                    ],
                    "detailed_feedback": "The code shows good understanding of backend principles. The architecture is clean with proper separation between layers. However, the implementation is missing some key patterns like repository pattern and comprehensive testing.",
                    "suggestions": [
                        "Implement repository pattern",
                        "Add more comprehensive tests",
                        "Integrate Redis for caching"
                    ],
                    "penalty_breakdown": {
                        "issues_found": [
                            {
                                "issue": "Minor security concern in error handling",
                                "severity": "low",
                                "penalty": 10
                            }
                        ],
                        "total_penalty": 10
                    }
                }"""
            }
        }],
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500
        }
    }


@pytest.fixture
def mock_telegram_update():
    """Mock Telegram update object."""
    update = MagicMock()
    update.effective_user.id = int(TEST_USER_ID)
    update.effective_user.username = TEST_USERNAME
    update.effective_chat.id = int(TEST_USER_ID)
    update.message.text = TEST_REPO_URL
    update.message.reply_text = AsyncMock()
    update.message.reply_chat_action = AsyncMock()
    return update


@pytest.fixture
def mock_telegram_context():
    """Mock Telegram context object."""
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.bot.edit_message_text = AsyncMock()
    context.bot.delete_message = AsyncMock()
    context.user_data = {}
    context.args = []
    return context


# Sample Data

@pytest.fixture
def sample_code_files():
    """Sample code files for testing repository processing."""
    return {
        "main.py": {
            "content": """#!/usr/bin/env python3
\"\"\"
Main application entry point.
\"\"\"

import asyncio
import logging
from typing import Optional

from src.config import Config
from src.database import Database
from src.server import create_server

logger = logging.getLogger(__name__)


async def main():
    \"\"\"Main application function.\"\"\"
    config = Config()
    
    # Initialize database
    db = Database(config.database_url)
    await db.initialize()
    
    # Create and start server
    server = create_server(config, db)
    
    logger.info("Starting server on %s:%d", config.host, config.port)
    await server.start()


if __name__ == "__main__":
    asyncio.run(main())
""",
            "language": "python",
            "priority": "critical"
        },
        
        "src/models.py": {
            "content": """\"\"\"
Database models using SQLAlchemy.
\"\"\"

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(Base):
    \"\"\"User model.\"\"\"
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Post(Base):
    \"\"\"Post model.\"\"\"
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
""",
            "language": "python",
            "priority": "important"
        },
        
        "tests/test_models.py": {
            "content": """\"\"\"
Tests for database models.
\"\"\"

import pytest
from datetime import datetime
from src.models import User, Post


def test_user_creation():
    \"\"\"Test user model creation.\"\"\"
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password"
    )
    
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    assert user.is_active is True


def test_post_creation():
    \"\"\"Test post model creation.\"\"\"
    post = Post(
        title="Test Post",
        content="This is a test post content.",
        author_id=1
    )
    
    assert post.title == "Test Post"
    assert post.content == "This is a test post content."
    assert post.author_id == 1
""",
            "language": "python",
            "priority": "useful"
        },
        
        "requirements.txt": {
            "content": """fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.23
pydantic==2.5.0
python-multipart==0.0.6
python-jose==3.3.0
passlib==1.7.4
bcrypt==4.0.1
redis==5.0.1
pytest==7.4.3
pytest-asyncio==0.21.1
""",
            "language": "text",
            "priority": "important"
        },
        
        "README.md": {
            "content": """# Test Backend Application

A sample backend application built with FastAPI and SQLAlchemy.

## Features

- User authentication and management
- RESTful API endpoints
- Database integration with SQLAlchemy
- Redis caching
- Comprehensive testing

## Setup

1. Install dependencies: `pip install -r requirements.txt`
2. Run the application: `python main.py`
3. Run tests: `pytest`

## API Endpoints

- `GET /users` - List all users
- `POST /users` - Create new user  
- `GET /users/{id}` - Get user by ID
- `PUT /users/{id}` - Update user
- `DELETE /users/{id}` - Delete user

## Architecture

The application follows a layered architecture with:

- Models layer (SQLAlchemy models)
- Service layer (business logic)
- API layer (FastAPI routes)
- Database layer (repository pattern)
""",
            "language": "markdown",
            "priority": "useful"
        }
    }


@pytest.fixture
def sample_invalid_json_responses():
    """Sample invalid JSON responses for testing recovery."""
    return [
        # Missing closing brace
        '{"requirements_met": {"test": true}, "scores": {"quality": 80}',
        
        # Malformed JSON with extra commas
        '{"requirements_met": {"test": true,}, "scores": {"quality": 80,}}',
        
        # JSON wrapped in markdown
        '''```json
        {
            "requirements_met": {"test": true},
            "scores": {"quality": 80},
            "recommendation": "yes"
        }
        ```''',
        
        # JSON with comments
        '''{
            // This is a comment
            "requirements_met": {"test": true},
            "scores": {"quality": 80},
            /* Multi-line comment */
            "recommendation": "yes"
        }''',
        
        # Truncated JSON
        '{"requirements_met": {"architectural_pattern": true, "repository_pattern": false}, "scores": {"task_completion": 75, "code_quality":'
    ]


# Test Utilities

def create_mock_aiohttp_response(status: int = 200, json_data: Dict[str, Any] = None, text_data: str = None):
    """Create a mock aiohttp response."""
    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.headers = {}
    
    if json_data:
        mock_response.json = AsyncMock(return_value=json_data)
    
    if text_data:
        mock_response.text = AsyncMock(return_value=text_data)
    
    return mock_response


def create_test_database_url() -> str:
    """Create a unique test database URL."""
    return f"sqlite:///:memory:"


async def wait_for_condition(condition_func, timeout: float = 5.0, interval: float = 0.1):
    """Wait for a condition to be true with timeout."""
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if await condition_func() if asyncio.iscoroutinefunction(condition_func) else condition_func():
            return True
        await asyncio.sleep(interval)
    
    return False


# Cleanup fixtures

@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Automatically cleanup temporary files after each test."""
    yield
    # Cleanup is handled by temp_directory fixture