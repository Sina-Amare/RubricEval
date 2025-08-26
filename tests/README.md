# CV Review Bot Test Suite

This directory contains comprehensive tests for the CV Review Bot application, ensuring reliability and quality across all components.

## Test Structure

### Core Test Files

- **`conftest.py`** - Shared fixtures, test configuration, and utilities
- **`test_core_models.py`** - Domain models and business logic tests
- **`test_utils.py`** - Utility functions and validation tests
- **`test_sqlite_adapter.py`** - SQLite storage adapter tests
- **`test_openrouter_adapter.py`** - OpenRouter LLM adapter tests
- **`test_bot_integration.py`** - Telegram bot integration tests

### Test Configuration

- **`pytest.ini`** - Pytest configuration with markers and options
- **`run_tests.py`** - Convenient test runner script

## Test Categories

### Unit Tests (`@pytest.mark.unit`)
- Individual component testing
- Pure function testing
- Model behavior validation
- Input validation testing

### Integration Tests (`@pytest.mark.integration`)  
- Component interaction testing
- API integration testing
- Workflow testing
- End-to-end scenarios

### Database Tests (`@pytest.mark.database`)
- Database operations
- Data persistence
- Transaction handling
- Data integrity

## Running Tests

### Quick Commands

```bash
# Run all tests
pytest

# Run specific category
pytest -m unit
pytest -m integration
pytest -m database

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_core_models.py

# Run specific test function
pytest tests/test_utils.py::TestGitHubValidation::test_valid_github_urls
```

### Using the Test Runner

```bash
# Run all tests with coverage
python run_tests.py all

# Run only unit tests
python run_tests.py unit

# Run integration tests
python run_tests.py integration

# Run specific test file
python run_tests.py specific --file test_core_models.py

# Verbose output
python run_tests.py all --verbose

# Generate coverage report
python run_tests.py coverage
```

## Test Coverage Goals

- **Minimum Coverage**: 80% overall
- **Critical Paths**: 95% coverage
- **Unit Tests**: 90% coverage
- **Integration Tests**: 70% coverage

### Coverage Areas

| Component | Target Coverage | Priority |
|-----------|----------------|----------|
| Core Models | 95% | Critical |
| Validators | 90% | High |
| Storage Adapters | 85% | High |  
| LLM Adapters | 80% | Medium |
| Bot Handlers | 75% | Medium |
| Utilities | 85% | High |

## Test Data and Fixtures

### Shared Fixtures (conftest.py)

- **Database Fixtures**: In-memory SQLite for testing
- **Mock Objects**: External service mocks
- **Sample Data**: Realistic test data
- **Environment Setup**: Test configuration

### Key Fixtures

```python
# Database testing
@pytest.fixture
def test_db_session():
    """Provides clean database session for each test"""

# Sample data
@pytest.fixture  
def sample_submission():
    """Creates sample submission object"""

@pytest.fixture
def sample_analysis_result():
    """Creates sample analysis result"""

# Mock services
@pytest.fixture
def mock_openrouter_response():
    """Mock OpenRouter API response"""

@pytest.fixture
def mock_telegram_update():
    """Mock Telegram update object"""
```

## Mocking Strategy

### External Services

All external services are mocked in tests:

- **Telegram Bot API**: Mocked using AsyncMock
- **OpenRouter API**: Mocked HTTP responses  
- **GitHub API**: Mocked repository data
- **Database**: Uses in-memory SQLite
- **File System**: Uses temporary directories

### Mock Patterns

```python
# Async service mocking
with patch.object(adapter, 'make_api_request') as mock_request:
    mock_request.return_value = expected_response
    result = await adapter.analyze_code(request)

# Database operation mocking  
with patch('adapters.storage.sqlite.SQLiteAdapter.create_submission') as mock_create:
    mock_create.return_value = expected_submission
    result = await adapter.create_submission(submission)

# Exception testing
mock_service.side_effect = ServiceError("Connection failed")
with pytest.raises(ServiceError):
    await service.method()
```

## Best Practices

### Test Organization

1. **Group Related Tests**: Use test classes to organize related tests
2. **Descriptive Names**: Test names should clearly describe what is being tested
3. **Arrange-Act-Assert**: Follow AAA pattern for test structure
4. **Single Responsibility**: Each test should verify one specific behavior

### Test Data

1. **Realistic Data**: Use data that resembles production scenarios
2. **Edge Cases**: Include boundary conditions and edge cases
3. **Invalid Data**: Test error handling with invalid inputs
4. **Isolation**: Each test should use independent data

### Async Testing

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async operations properly"""
    result = await async_function()
    assert result.success
```

### Error Testing

```python
def test_error_handling():
    """Test that errors are handled gracefully"""
    with pytest.raises(ExpectedError, match="expected message"):
        function_that_should_fail()
```

## Continuous Integration

### Pre-commit Hooks

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

### CI Pipeline

Tests are run automatically on:
- Pull requests
- Main branch commits
- Scheduled runs (daily)

### Required Checks

-  All tests pass
-  Coverage >= 80%
-  No linting errors
-  Type checking passes

## Debugging Tests

### Common Issues

1. **Import Errors**: Ensure `src` is in Python path
2. **Async Issues**: Use `@pytest.mark.asyncio` for async tests
3. **Database Issues**: Ensure test database is properly isolated
4. **Mock Issues**: Verify mock patches are applied correctly

### Debugging Commands

```bash
# Run tests with detailed output
pytest -v -s tests/test_specific.py

# Run single test with debugging
pytest -v -s tests/test_file.py::TestClass::test_method

# Drop into debugger on failure
pytest --pdb

# Show local variables on failure
pytest -l

# Trace execution
pytest --trace
```

## Performance Testing

### Load Testing

```python
@pytest.mark.slow
async def test_concurrent_submissions():
    """Test handling multiple concurrent requests"""
    tasks = [submit_request() for _ in range(10)]
    results = await asyncio.gather(*tasks)
    assert all(r.success for r in results)
```

### Memory Testing

```python
def test_memory_usage():
    """Test that operations don't cause memory leaks"""
    import tracemalloc
    tracemalloc.start()
    
    # Perform operations
    perform_operations()
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    assert peak < 100 * 1024 * 1024  # Less than 100MB
```

## Test Maintenance

### Regular Tasks

1. **Review Coverage**: Check coverage reports monthly
2. **Update Test Data**: Keep test data current with requirements
3. **Cleanup Obsolete Tests**: Remove tests for removed features
4. **Performance Review**: Monitor test execution times

### Test Refactoring

When refactoring tests:
1. Maintain test coverage levels
2. Preserve test intent and behavior
3. Update documentation
4. Consider impact on CI pipeline

## Contributing to Tests

### Adding New Tests

1. Choose appropriate test file
2. Use existing fixtures when possible
3. Follow naming conventions
4. Add appropriate markers
5. Update coverage goals if needed

### Test Review Checklist

- [ ] Tests follow AAA pattern
- [ ] Descriptive test names
- [ ] Appropriate fixtures used
- [ ] Error cases covered
- [ ] Mock usage is appropriate
- [ ] Coverage impact assessed