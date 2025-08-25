# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an Automated Recruitment Screening System that streamlines technical candidate evaluation through a Telegram bot interface. The system accepts GitHub repository submissions, analyzes code quality using LLMs, and provides consistent hiring recommendations.

## Technology Stack

- **Language**: Python 3.11+
- **Bot Framework**: python-telegram-bot v20.x
- **Database**: SQLite (embedded, zero-config)
- **LLM Integration**: OpenRouter API (unified access to Gemini, GPT-4, Claude)
- **Async Processing**: Python asyncio (no external queue needed)
- **Repository Operations**: GitPython

## Development Setup and Commands

### Virtual Environment

- Activate: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
- Deactivate: `deactivate`

### Common Development Commands

- Install dependencies: `pip install -r requirements.txt`
- Save dependencies: `pip freeze > requirements.txt`
- Run bot: `python src/bot.py`
- Run tests: `python -m pytest tests/ -v`
- Format code: `python -m black src/ tests/`
- Lint code: `python -m flake8 src/ tests/`
- Type check: `python -m mypy src/`
- Database setup: `python scripts/setup_db.py`

## Project Structure

```
cv_review/
├── venv/                    # Virtual environment
├── src/
│   ├── bot.py                 # Main Telegram bot entry point
│   ├── analyzer.py            # LLM analysis orchestrator
│   ├── repo_processor.py      # Repository cloning & file extraction
│   ├── database.py            # SQLite models & operations
│   ├── config.py              # Configuration with defaults
│   └── utils/
│       ├── token_counter.py   # Token estimation for LLMs
│       ├── file_filter.py     # Smart file selection by role
│       ├── validators.py      # Input validation
│       └── logger.py          # Logging configuration
├── tests/                  # Test suite
├── data/
│   ├── task_descriptions/  # Role-specific requirements
│   └── reports/            # Generated reports backup
├── scripts/
│   ├── setup_db.py
│   └── test_bot.py
├── requirements.txt
├── .env.example
└── docker-compose.yml
```

## Core Development Principles

### 1. Simplicity First

- Start with the simplest solution that works
- Only add complexity when absolutely necessary
- Prefer readable code over clever optimizations
- Use existing libraries rather than reinventing wheels

### 2. Robustness & Error Handling

- Every external API call must have retry logic
- All user inputs must be validated
- Implement fallback mechanisms for critical paths
- Log errors comprehensively but securely
- Never let the bot crash - graceful degradation preferred

### 3. Code Quality Standards

- Type hints for all function parameters and returns
- Docstrings for all public functions and classes
- Maximum function length: 50 lines
- Maximum file length: 500 lines
- Test coverage minimum: 80%
- All database queries must use parameterized statements

### 4. Security Guidelines

- Never log sensitive data (API keys, user tokens)
- Validate and sanitize all GitHub URLs
- Use environment variables for all secrets
- Implement rate limiting on all endpoints
- Regular dependency updates for security patches

### 5. Performance Considerations

- Database queries must use appropriate indexes
- Implement caching for frequently accessed data
- Use async/await for I/O operations
- Chunk large code repositories for analysis
- Monitor memory usage during repository processing

## Critical Implementation Rules

1. **LLM Token Management**

   - Always estimate tokens before API calls
   - Implement chunking for repositories >100k tokens
   - Cache analysis results for 24 hours
   - Use structured output format (JSON) for consistency

2. **Telegram Bot Best Practices**

   - Response time <3 seconds for all commands
   - Use inline keyboards for better UX
   - Implement conversation timeouts (5 minutes)
   - Handle message size limits (4096 chars)
   - Provide clear error messages to users

3. **Database Design**

   - Use UUIDs for public-facing IDs
   - Implement soft deletes for audit trail
   - Index on: telegram_user_id, status, created_at
   - Regular backups every 6 hours
   - Connection pooling with max 20 connections

4. **Testing Requirements**

   - Unit tests for all business logic
   - Integration tests for external APIs
   - Mock all external services in tests
   - Test error paths explicitly
   - Load test with 100 concurrent submissions

5. **Monitoring & Observability**
   - Log all state transitions
   - Track analysis duration metrics
   - Alert on >3 consecutive failures
   - Daily report of success/failure rates
   - Monitor LLM API costs

## Environment Variables Required

```bash
# Manager Configuration (Required - only 2!)
BOT_TOKEN=your_telegram_bot_token
OPENROUTER_KEY=your_openrouter_api_key

# Developer Configuration (Optional - has defaults)
DATABASE_PATH=./data/reviews.db
MAX_REPO_SIZE_MB=100
ANALYSIS_TIMEOUT=600
MAX_CONCURRENT=3
PRIMARY_MODEL=google/gemini-2.5-flash
FALLBACK_MODEL=openai/gpt-4.1-mini
MAX_TOKENS=900000
TEMPERATURE=0.2
MANAGER_IDS=123456789,987654321  # Telegram user IDs
```

## Deployment Checklist

- [ ] BOT_TOKEN and OPENROUTER_KEY configured in .env
- [ ] Docker and docker-compose installed
- [ ] Task requirement files created (backend_task.md, frontend_task.md)
- [ ] Manager IDs configured (if using manager commands)
- [ ] Run `docker-compose up -d` to start
- [ ] Check logs with `docker-compose logs -f`
- [ ] Test bot with `/start` command
- [ ] Verify database created in data/ folder

## Common Issues & Solutions

1. **Token Limit Exceeded**

   - Solution: Implement file filtering to exclude non-source files
   - Fallback: Analyze only main application files

2. **Repository Clone Timeout**

   - Solution: Use shallow clone (depth=1)
   - Fallback: Fetch files via GitHub API

3. **LLM API Rate Limiting**

   - Solution: Implement exponential backoff
   - Fallback: Queue for later processing

4. **Database Connection Pool Exhausted**

   - Solution: Increase pool size or optimize queries
   - Monitor: Track active connections

5. **Telegram Message Too Long**
   - Solution: Split into multiple messages
   - Alternative: Provide summary with full report link

# Additional Rules

- **Reference Key Documents**: Always review the following documents to understand the project context and objectives:

  - `@technical_implementation_plan.md`
  - `@workflow_non_technical.md`
  - `@first_thoughts.md`
  - `@CLAUDE.md`

- **Code Documentation**: Include docstrings and comments in all code, adhering to best practices for clarity and maintainability.

- **Logging System**: Design and implement a robust logging system following best practices to ensure effective monitoring, debugging, and maintenance.

- **Use Specialized Agents**: When working on complex tasks, proactively use specialized subagents via the Task tool when they match the task requirements. For example:

  - Use `architecture-agent` for system design and architectural decisions
  - Use `backend-specialist` for server-side logic and API design
  - Use `frontend-specialist` for UI/UX implementation
  - Use `refactor-specialist` for code optimization and restructuring
  - Use `tester` for test creation and validation
  - Leverage agents working in parallel when tasks are independent

- **Test After Implementation**: Test each component immediately after implementation before moving to the next component. This ensures:

  - Early detection of issues
  - Validation of functionality
  - Confidence in the codebase
  - Always run tests after completing a module or significant feature
  - ALWAYS activate virtual environment before running tests: `source venv/bin/activate`

- **Proactive Commit Management**: Ask the user to commit changes at appropriate checkpoints based on best practices:
  - After completing a major feature or module
  - Before starting a significant refactoring
  - After successful testing of components
  - When switching between different areas of work
  - Before any risky operations

## Development Workflow with User

### Credential Management

- **Never hardcode credentials** - Always use environment variables
- **When credentials are needed**:
  1. PAUSE implementation
  2. Ask user to provide specific credential with clear instructions
  3. WAIT for user confirmation
  4. Only then proceed with implementation

### User Action Protocol

When user action is required:

1. **PAUSE** current task
2. **PROVIDE** clear, step-by-step instructions
3. **WAIT** for user to complete and confirm
4. **CONTINUE** only after confirmation

### Examples of User Actions:

- **Creating Telegram Bot**: "Please create a Telegram bot using BotFather. Instructions: [step-by-step guide]. Let me know when done and provide the BOT_TOKEN."
- **Getting API Keys**: "Please obtain OpenRouter API key from [website]. Let me know when you have it."
- **Installing Packages**: "Please run: `pip install [packages]` in your terminal. Confirm when installation is complete."
- **Testing Setup**: "Please test [specific feature]. Let me know if it works or any errors you encounter."

### Development Responsibilities

- **Claude Code handles**: All code implementation, documentation, configuration files
- **User handles**: Environment setup, credential acquisition, package installation, testing
