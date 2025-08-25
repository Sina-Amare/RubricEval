# Technical Implementation Plan - Simplified CV Review Bot

## Technology Stack (Minimal & Robust)

### Core Technologies
- **Language**: Python 3.11+
- **Bot Framework**: python-telegram-bot v20.x
- **Database**: SQLite (embedded, zero-config)
- **LLM Access**: OpenRouter API (unified access to multiple models)
- **Async Processing**: Python asyncio (no Celery/Redis needed)
- **Repository Operations**: GitPython
- **Deployment**: Single Docker container

### Dependencies
```
python-telegram-bot==20.7
openai==1.12.0         # Works with OpenRouter
gitpython==3.1.42
sqlalchemy==2.0.27
python-dotenv==1.0.1
aiohttp==3.9.3
tiktoken==0.5.2        # Token counting
pydantic==2.6.1
```

## Project Structure (Clean & Modular)

```
cv_review/
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
├── data/
│   ├── reviews.db             # SQLite database (auto-created)
│   ├── task_requirements/
│   │   ├── backend_task.md    # Go backend requirements
│   │   └── frontend_task.md   # Frontend requirements
│   └── reports/               # JSON report backups
├── .env.example               # Template for manager (2 variables)
├── .env                       # Actual configuration
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Implementation Timeline (8 Hours)

### Hour 1: Foundation & Setup
```python
# config.py - Smart configuration with defaults
import os
from dotenv import load_dotenv

load_dotenv()

# Manager-configured (required)
BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENROUTER_KEY = os.getenv('OPENROUTER_KEY')

# Developer-configured (with defaults)
DATABASE_PATH = os.getenv('DATABASE_PATH', './data/reviews.db')
MAX_REPO_SIZE_MB = int(os.getenv('MAX_REPO_SIZE_MB', '100'))
ANALYSIS_TIMEOUT = int(os.getenv('ANALYSIS_TIMEOUT', '600'))
MAX_CONCURRENT = int(os.getenv('MAX_CONCURRENT', '3'))

# LLM Configuration
PRIMARY_MODEL = os.getenv('PRIMARY_MODEL', 'google/gemini-flash-1.5-8b')
FALLBACK_MODEL = os.getenv('FALLBACK_MODEL', 'openai/gpt-4-turbo-preview')
MAX_TOKENS = int(os.getenv('MAX_TOKENS', '900000'))
TEMPERATURE = float(os.getenv('TEMPERATURE', '0.2'))

# Repository Processing
TEMP_DIR = os.getenv('TEMP_DIR', '/tmp/repos')
CLONE_TIMEOUT = int(os.getenv('CLONE_TIMEOUT', '60'))
CACHE_DURATION = int(os.getenv('CACHE_DURATION', '3600'))

# File Patterns
BACKEND_PATTERNS = {
    'critical': ['main.go', 'cmd/**/*.go', 'handler/**/*.go', 'api/**/*.go'],
    'important': ['service/**/*.go', 'model/**/*.go', 'repository/**/*.go'],
    'useful': ['**/*_test.go', 'go.mod', 'go.sum', 'README.md'],
    'exclude': ['vendor/**', '.git/**', '**/*.pb.go']
}

FRONTEND_PATTERNS = {
    'critical': ['src/App.*', 'src/index.*', 'src/main.*', 'pages/**/*'],
    'important': ['components/**/*', 'services/**/*', 'hooks/**/*'],
    'useful': ['**/*.test.*', 'package.json', '*.config.js', 'README.md'],
    'exclude': ['node_modules/**', 'build/**', 'dist/**', '.git/**']
}
```

### Hour 2: Database Schema & Models
```python
# database.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

Base = declarative_base()
engine = create_engine(f'sqlite:///{DATABASE_PATH}')
Session = sessionmaker(bind=engine)

class Submission(Base):
    __tablename__ = 'submissions'
    
    id = Column(Integer, primary_key=True)
    telegram_user_id = Column(String, nullable=False)
    telegram_username = Column(String)
    github_url = Column(String, nullable=False)
    role = Column(String, nullable=False)  # 'backend' or 'frontend'
    status = Column(String, default='pending')  # pending, analyzing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
class Report(Base):
    __tablename__ = 'reports'
    
    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, nullable=False)
    analysis_result = Column(Text)  # JSON string
    recommendation = Column(String)  # ACCEPT or REJECT
    confidence = Column(Float)
    completeness_score = Column(Float)
    quality_score = Column(Float)
    architecture_score = Column(Float)
    testing_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def get_analysis(self):
        return json.loads(self.analysis_result) if self.analysis_result else {}

# Create tables
Base.metadata.create_all(engine)
```

### Hour 3: Telegram Bot Core
```python
# bot.py
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from database import Session, Submission, Report
import repo_processor
import analyzer

# Conversation states
WAITING_URL, WAITING_ROLE = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome to CV Review Bot! 🤖\n\n"
        "Please send me your GitHub repository URL for review."
    )
    context.user_data['state'] = WAITING_URL

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    
    if state == WAITING_URL:
        url = update.message.text.strip()
        
        # Validate GitHub URL
        if not validate_github_url(url):
            await update.message.reply_text(
                "❌ Please provide a valid GitHub repository URL.\n"
                "Format: https://github.com/username/repository"
            )
            return
        
        context.user_data['github_url'] = url
        
        # Role selection keyboard
        keyboard = [
            [InlineKeyboardButton("Backend (Go)", callback_data="role_backend")],
            [InlineKeyboardButton("Frontend", callback_data="role_frontend")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Repository received! ✅\n"
            "Please select the role you're applying for:",
            reply_markup=reply_markup
        )
        context.user_data['state'] = WAITING_ROLE

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('role_'):
        role = query.data.replace('role_', '')
        github_url = context.user_data.get('github_url')
        
        # Save submission to database
        session = Session()
        submission = Submission(
            telegram_user_id=str(update.effective_user.id),
            telegram_username=update.effective_user.username,
            github_url=github_url,
            role=role,
            status='pending'
        )
        session.add(submission)
        session.commit()
        submission_id = submission.id
        session.close()
        
        await query.edit_message_text(
            f"✅ Submission received!\n"
            f"📋 Tracking ID: #{submission_id}\n"
            f"🔄 Status: Analyzing...\n\n"
            f"I'll analyze your code and notify you when done."
        )
        
        # Start async analysis
        asyncio.create_task(analyze_submission(submission_id, update.effective_user.id))
        
        # Reset conversation
        context.user_data.clear()

async def analyze_submission(submission_id: int, user_id: int):
    """Background task to analyze submission"""
    try:
        session = Session()
        submission = session.query(Submission).get(submission_id)
        submission.status = 'analyzing'
        session.commit()
        
        # Process repository
        repo_content = await repo_processor.process_repository(
            submission.github_url,
            submission.role
        )
        
        # Analyze with LLM
        analysis_result = await analyzer.analyze_code(
            repo_content,
            submission.role
        )
        
        # Save report
        report = Report(
            submission_id=submission_id,
            analysis_result=json.dumps(analysis_result),
            recommendation=analysis_result['recommendation'],
            confidence=analysis_result['confidence'],
            completeness_score=analysis_result['scores']['completeness'],
            quality_score=analysis_result['scores']['quality'],
            architecture_score=analysis_result['scores']['architecture'],
            testing_score=analysis_result['scores']['testing']
        )
        session.add(report)
        
        submission.status = 'completed'
        submission.completed_at = datetime.utcnow()
        session.commit()
        session.close()
        
        # Notify user
        await notify_user(user_id, submission_id, analysis_result)
        
    except Exception as e:
        logger.error(f"Analysis failed for submission {submission_id}: {e}")
        session = Session()
        submission = session.query(Submission).get(submission_id)
        submission.status = 'failed'
        session.commit()
        session.close()

# Manager commands
async def reports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_manager(update.effective_user.id):
        await update.message.reply_text("Unauthorized")
        return
    
    session = Session()
    recent_reports = session.query(Report).order_by(Report.created_at.desc()).limit(10).all()
    
    for report in recent_reports:
        submission = session.query(Submission).get(report.submission_id)
        text = format_report_summary(submission, report)
        await update.message.reply_text(text, parse_mode='Markdown')
    
    session.close()

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reports", reports_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    application.run_polling()

if __name__ == '__main__':
    main()
```

### Hour 4-5: Repository Processing & Token Optimization
```python
# repo_processor.py
import os
import tempfile
import shutil
from git import Repo
from pathlib import Path
import tiktoken
from typing import List, Dict, Tuple

class RepositoryProcessor:
    def __init__(self, role: str, max_tokens: int = 900000):
        self.role = role
        self.max_tokens = max_tokens
        self.encoder = tiktoken.encoding_for_model("gpt-4")
        self.patterns = BACKEND_PATTERNS if role == 'backend' else FRONTEND_PATTERNS
    
    async def process_repository(self, github_url: str) -> Dict:
        """Clone and process repository for LLM analysis"""
        temp_dir = None
        try:
            # Clone repository
            temp_dir = tempfile.mkdtemp(prefix='cv_review_')
            repo = Repo.clone_from(github_url, temp_dir, depth=1)
            
            # Check repository size
            repo_size = self._get_dir_size(temp_dir)
            if repo_size > MAX_REPO_SIZE_MB * 1024 * 1024:
                logger.warning(f"Repository too large: {repo_size / 1024 / 1024:.2f}MB")
            
            # Extract and prioritize files
            files = self._extract_files(temp_dir)
            
            # Optimize for token limit
            optimized_content = self._optimize_for_context(files)
            
            return {
                'success': True,
                'content': optimized_content,
                'file_count': len(files),
                'total_tokens': self._count_tokens(optimized_content)
            }
            
        except Exception as e:
            logger.error(f"Repository processing failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def _extract_files(self, repo_path: str) -> List[Dict]:
        """Extract files based on role patterns"""
        files = []
        repo_path = Path(repo_path)
        
        # Categorize files by priority
        critical_files = []
        important_files = []
        useful_files = []
        
        for pattern_type, patterns in [
            ('critical', self.patterns['critical']),
            ('important', self.patterns['important']),
            ('useful', self.patterns['useful'])
        ]:
            for pattern in patterns:
                for file_path in repo_path.glob(pattern):
                    if file_path.is_file() and not self._should_exclude(file_path):
                        content = self._read_file_safe(file_path)
                        if content:
                            file_dict = {
                                'path': str(file_path.relative_to(repo_path)),
                                'content': content,
                                'priority': pattern_type,
                                'tokens': self._count_tokens(content)
                            }
                            
                            if pattern_type == 'critical':
                                critical_files.append(file_dict)
                            elif pattern_type == 'important':
                                important_files.append(file_dict)
                            else:
                                useful_files.append(file_dict)
        
        # Combine in priority order
        files = critical_files + important_files + useful_files
        return files
    
    def _optimize_for_context(self, files: List[Dict]) -> str:
        """Optimize file content for LLM context window"""
        optimized_content = []
        current_tokens = 0
        
        # Add task requirements first (reserved 2000 tokens)
        task_requirements = self._load_task_requirements()
        optimized_content.append(f"# Task Requirements\n{task_requirements}\n")
        current_tokens += 2000
        
        # Add repository structure (reserved 1000 tokens)
        structure = self._generate_tree_structure(files)
        optimized_content.append(f"# Repository Structure\n{structure}\n")
        current_tokens += 1000
        
        # Add files by priority
        for file in files:
            file_tokens = file['tokens']
            
            # Check if we can fit the entire file
            if current_tokens + file_tokens < self.max_tokens - 5000:  # Leave buffer
                optimized_content.append(f"\n## File: {file['path']}\n```\n{file['content']}\n```\n")
                current_tokens += file_tokens
            elif file['priority'] == 'critical':
                # For critical files, include partial content if needed
                available_tokens = self.max_tokens - current_tokens - 5000
                if available_tokens > 1000:
                    truncated = self._truncate_to_tokens(file['content'], available_tokens)
                    optimized_content.append(f"\n## File: {file['path']} (truncated)\n```\n{truncated}\n```\n")
                    current_tokens += available_tokens
                    break
        
        return '\n'.join(optimized_content)
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encoder.encode(text))
    
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token limit"""
        tokens = self.encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text
        truncated_tokens = tokens[:max_tokens]
        return self.encoder.decode(truncated_tokens)
```

### Hour 6: LLM Integration with Smart Fallbacks
```python
# analyzer.py
import aiohttp
import json
from typing import Dict, Optional
import asyncio

class CodeAnalyzer:
    def __init__(self):
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {OPENROUTER_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/cv-review-bot",
            "X-Title": "CV Review Bot"
        }
        self.models = [
            {"name": PRIMARY_MODEL, "context": 1000000},
            {"name": FALLBACK_MODEL, "context": 128000},
            {"name": "openai/gpt-3.5-turbo-16k", "context": 16000}
        ]
    
    async def analyze_code(self, repo_content: Dict, role: str) -> Dict:
        """Analyze code with LLM using fallback chain"""
        
        for model in self.models:
            try:
                # Adjust content if needed for smaller context
                content = repo_content['content']
                if repo_content['total_tokens'] > model['context'] * 0.9:
                    content = self._reduce_content_for_model(content, model['context'])
                
                result = await self._call_llm(content, role, model['name'])
                if result:
                    return result
                    
            except Exception as e:
                logger.warning(f"Model {model['name']} failed: {e}")
                continue
        
        # All models failed
        raise Exception("All LLM models failed to analyze code")
    
    async def _call_llm(self, content: str, role: str, model: str) -> Optional[Dict]:
        """Make API call to OpenRouter"""
        
        prompt = self._build_prompt(content, role)
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert code reviewer evaluating candidates for technical positions."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": TEMPERATURE,
            "response_format": {"type": "json_object"}
        }
        
        async with aiohttp.ClientSession() as session:
            for attempt in range(3):  # Retry logic
                try:
                    async with session.post(
                        self.openrouter_url,
                        headers=self.headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            result = json.loads(data['choices'][0]['message']['content'])
                            return self._validate_result(result)
                        elif response.status == 429:  # Rate limit
                            await asyncio.sleep(2 ** attempt)
                        else:
                            logger.error(f"API error: {response.status}")
                            
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout on attempt {attempt + 1}")
                    continue
        
        return None
    
    def _build_prompt(self, content: str, role: str) -> str:
        """Build analysis prompt"""
        return f"""
Analyze this {role} code submission against the task requirements provided.

{content}

Evaluate the submission on these criteria:
1. **Requirement Completeness** (0-100): Are all required features implemented?
2. **Code Quality** (0-100): Is the code clean, readable, and maintainable?
3. **Architecture** (0-100): Is the structure logical and scalable?
4. **Testing** (0-100): Are there adequate tests?

Provide your analysis in this exact JSON format:
{{
    "requirements_met": {{
        "feature1": true/false,
        "feature2": true/false,
        // ... for each requirement
    }},
    "scores": {{
        "completeness": 0-100,
        "quality": 0-100,
        "architecture": 0-100,
        "testing": 0-100
    }},
    "strengths": ["strength1", "strength2", ...],
    "weaknesses": ["weakness1", "weakness2", ...],
    "critical_issues": ["issue1", "issue2", ...],
    "recommendation": "ACCEPT" or "REJECT",
    "confidence": 0-100,
    "detailed_feedback": "Detailed explanation of the decision"
}}
"""
    
    def _validate_result(self, result: Dict) -> Dict:
        """Validate and normalize LLM response"""
        required_keys = ['requirements_met', 'scores', 'recommendation', 'confidence']
        
        for key in required_keys:
            if key not in result:
                raise ValueError(f"Missing required key: {key}")
        
        # Ensure recommendation is valid
        if result['recommendation'] not in ['ACCEPT', 'REJECT']:
            result['recommendation'] = 'REJECT'
        
        # Ensure confidence is within range
        result['confidence'] = max(0, min(100, result['confidence']))
        
        return result
```

### Hour 7: Async Processing & Report Generation
```python
# Add to bot.py - Background processing without Celery

import asyncio
from concurrent.futures import ThreadPoolExecutor

# Global executor for managing concurrent analyses
executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT)
analysis_queue = asyncio.Queue(maxsize=10)

async def process_queue():
    """Background worker to process analysis queue"""
    while True:
        try:
            submission_id = await analysis_queue.get()
            await analyze_submission(submission_id)
        except Exception as e:
            logger.error(f"Queue processing error: {e}")
        finally:
            analysis_queue.task_done()

async def notify_user(user_id: int, submission_id: int, analysis: Dict):
    """Send analysis results to user"""
    
    # Format report
    report_text = f"""
📊 **Analysis Complete!**

**Submission ID**: #{submission_id}
**Recommendation**: {analysis['recommendation']} 
**Confidence**: {analysis['confidence']}%

**Scores**:
• Completeness: {analysis['scores']['completeness']}/100
• Code Quality: {analysis['scores']['quality']}/100
• Architecture: {analysis['scores']['architecture']}/100
• Testing: {analysis['scores']['testing']}/100

**Strengths**:
{format_list(analysis.get('strengths', []))}

**Areas for Improvement**:
{format_list(analysis.get('weaknesses', []))}

**Decision**: {analysis['detailed_feedback'][:500]}...
"""
    
    # Send to user
    await application.bot.send_message(
        chat_id=user_id,
        text=report_text,
        parse_mode='Markdown'
    )
    
    # Notify managers
    for manager_id in MANAGER_IDS:
        summary = f"New submission reviewed: #{submission_id} - {analysis['recommendation']}"
        await application.bot.send_message(chat_id=manager_id, text=summary)

def format_report_summary(submission: Submission, report: Report) -> str:
    """Format report for manager view"""
    analysis = report.get_analysis()
    
    return f"""
📋 **Report #{submission.id}**
👤 User: @{submission.telegram_username or 'Unknown'}
🎯 Role: {submission.role.title()}
🔗 Repo: {submission.github_url}
📅 Date: {submission.created_at.strftime('%Y-%m-%d %H:%M')}

**Scores**:
• Completeness: {report.completeness_score:.0f}/100
• Quality: {report.quality_score:.0f}/100
• Architecture: {report.architecture_score:.0f}/100
• Testing: {report.testing_score:.0f}/100

**Recommendation**: {report.recommendation}
**Confidence**: {report.confidence:.0f}%
"""
```

### Hour 8: Docker Setup & Testing
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install git for repository cloning
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY data/task_requirements/ ./data/task_requirements/

# Create data directories
RUN mkdir -p data/reports /tmp/repos

# Run bot
CMD ["python", "src/bot.py"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  bot:
    build: .
    container_name: cv_review_bot
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - OPENROUTER_KEY=${OPENROUTER_KEY}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    networks:
      - cv_review_network

networks:
  cv_review_network:
    driver: bridge

volumes:
  data:
  logs:
```

```bash
# .env.example (For Manager)
# Required Configuration - Manager must set these
BOT_TOKEN=your_telegram_bot_token_here
OPENROUTER_KEY=your_openrouter_api_key_here

# Optional - Developer can customize these
# DATABASE_PATH=./data/reviews.db
# MAX_REPO_SIZE_MB=100
# PRIMARY_MODEL=google/gemini-flash-1.5-8b
# FALLBACK_MODEL=openai/gpt-4-turbo-preview
```

## Testing Strategy

### Unit Tests
```python
# tests/test_analyzer.py
import pytest
from unittest.mock import Mock, patch

class TestCodeAnalyzer:
    @pytest.mark.asyncio
    async def test_analyze_with_fallback(self):
        analyzer = CodeAnalyzer()
        
        # Mock first model failure, second success
        with patch.object(analyzer, '_call_llm') as mock_llm:
            mock_llm.side_effect = [
                Exception("Model 1 failed"),
                {"recommendation": "ACCEPT", "confidence": 85}
            ]
            
            result = await analyzer.analyze_code(
                {"content": "test", "total_tokens": 100},
                "backend"
            )
            
            assert result["recommendation"] == "ACCEPT"
            assert mock_llm.call_count == 2

class TestRepositoryProcessor:
    def test_token_counting(self):
        processor = RepositoryProcessor("backend")
        text = "Hello world"
        tokens = processor._count_tokens(text)
        assert tokens > 0
    
    def test_file_prioritization(self):
        processor = RepositoryProcessor("backend")
        files = [
            {"priority": "useful", "tokens": 100},
            {"priority": "critical", "tokens": 200},
            {"priority": "important", "tokens": 150}
        ]
        # Critical should come first
        sorted_files = sorted(files, key=lambda x: 
            ['critical', 'important', 'useful'].index(x['priority']))
        assert sorted_files[0]['priority'] == 'critical'
```

### Integration Tests
```python
# tests/test_integration.py
@pytest.mark.asyncio
async def test_full_submission_flow():
    # 1. Submit URL
    submission_id = await submit_repository(
        "https://github.com/test/repo",
        "backend"
    )
    
    # 2. Wait for analysis
    await asyncio.sleep(5)
    
    # 3. Check report exists
    report = get_report(submission_id)
    assert report is not None
    assert report.recommendation in ['ACCEPT', 'REJECT']
```

## Deployment Instructions

### For Manager (Simple)
```bash
# 1. Clone repository
git clone <repository-url>
cd cv_review

# 2. Configure environment
cp .env.example .env
# Edit .env - add BOT_TOKEN and OPENROUTER_KEY

# 3. Deploy
docker-compose up -d

# 4. Check logs
docker-compose logs -f

# Bot is ready!
```

### For Developer (Advanced)
```bash
# Development setup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure all variables
cp .env.example .env
# Edit .env with all configurations

# Run locally
python src/bot.py

# Run tests
pytest tests/ -v
```

## Monitoring & Maintenance

### Health Checks
```python
# Add to bot.py
async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple health check command"""
    checks = {
        "Database": check_database_connection(),
        "LLM API": await check_llm_api(),
        "Disk Space": check_disk_space(),
        "Queue Size": analysis_queue.qsize()
    }
    
    status = "\n".join([f"{k}: {'✅' if v else '❌'}" for k, v in checks.items()])
    await update.message.reply_text(f"System Status:\n{status}")
```

### Automatic Cleanup
```python
# Add to bot.py - Run daily
async def cleanup_old_data():
    """Clean up old temporary files and database entries"""
    while True:
        await asyncio.sleep(86400)  # Daily
        
        # Clean temp repos
        for temp_dir in Path('/tmp/repos').glob('cv_review_*'):
            if temp_dir.stat().st_mtime < time.time() - 3600:
                shutil.rmtree(temp_dir)
        
        # Archive old reports
        session = Session()
        old_date = datetime.utcnow() - timedelta(days=30)
        old_reports = session.query(Report).filter(Report.created_at < old_date).all()
        
        for report in old_reports:
            # Save to JSON backup
            backup_path = f"data/reports/archive_{report.id}.json"
            with open(backup_path, 'w') as f:
                json.dump(report.get_analysis(), f)
        
        session.close()
```

## Why This Simplified Approach Works

1. **No External Dependencies**: SQLite is embedded, no Redis/PostgreSQL needed
2. **Native Async**: Python's asyncio handles concurrency perfectly for our scale
3. **Smart Token Management**: Prioritized file loading maximizes LLM effectiveness
4. **Robust Fallbacks**: Multiple model options ensure high availability
5. **Simple Deployment**: Single container, two environment variables
6. **Cost Effective**: ~$0.10-0.30 per evaluation with smart model selection
7. **Maintainable**: Clean, modular code structure

## Performance Expectations

- **Concurrent Analyses**: 3 simultaneous (configurable)
- **Analysis Time**: 2-5 minutes typical
- **Memory Usage**: <512MB
- **Database Size**: ~1MB per 100 submissions
- **Success Rate**: >95% with fallback chain

## Next Steps After MVP

1. Add webhook support for better Telegram performance
2. Implement caching for duplicate submissions
3. Add more detailed logging and metrics
4. Create web dashboard for report viewing
5. Support additional programming languages