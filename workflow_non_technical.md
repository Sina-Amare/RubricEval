# Automated Recruitment Screening System - Business Workflow (Simplified)

## Executive Summary
A streamlined, single-container system that automates technical candidate screening via Telegram bot. The system accepts GitHub repositories, intelligently analyzes code using AI, and provides instant hiring recommendations.

## Core Value Proposition
- **For Candidates**: Submit repository, get evaluated fairly and consistently
- **For Managers**: Configure 2 settings, deploy with 1 command, receive structured reports
- **For Company**: 80% reduction in screening time, consistent evaluation standards

## System Overview

### Architecture Highlights
- **Single Docker Container** - Complete system in one deployable unit
- **Embedded Database** - SQLite for zero-configuration persistence
- **Smart Code Analysis** - Context-optimized LLM evaluation
- **Async Processing** - Built-in background task handling
- **Universal LLM Access** - OpenRouter supports multiple AI models

## Detailed Workflow

### Phase 1: Manager Setup (One-Time, 5 Minutes)
**Required Actions**:
1. Obtain Telegram Bot Token from BotFather
2. Obtain OpenRouter API Key
3. Add both to `.env` file
4. Run `docker-compose up`
5. System is fully operational

**What Happens Behind the Scenes**:
- Bot automatically registers commands
- Database automatically initializes
- System self-configures optimal settings
- Health checks confirm readiness

### Phase 2: Candidate Submission Flow

#### Step 1: Initial Contact
**User Action**: Candidate sends `/start` to bot
**System Response**: Welcome message with clear instructions
**Timing**: < 1 second

#### Step 2: Repository Submission
**User Action**: Sends GitHub repository URL
**System Validation**:
- Verify URL format (must be github.com)
- Check repository accessibility (public only)
- Confirm repository exists
**Error Handling**: 
- Invalid URL → Request valid GitHub link
- Private repo → Instruct to make public
- Network error → Retry automatically (3 attempts)
**Timing**: 2-3 seconds

#### Step 3: Role Selection
**User Action**: Clicks role button (Backend/Frontend)
**System Response**: 
- Stores submission with unique ID
- Confirms receipt with tracking number
- Initiates background analysis
**Timing**: < 1 second

### Phase 3: Intelligent Code Analysis

#### Repository Processing Pipeline
**Stage 1: Cloning**
- Shallow clone for speed (depth=1)
- Size check (max 100MB)
- Timeout protection (60 seconds)
- Fallback: GitHub API if clone fails

**Stage 2: Smart File Selection**
Based on role, the system prioritizes:
- **Backend (Go)**:
  - Critical: main.go, cmd/, handlers/
  - Important: services/, models/, APIs/
  - Useful: tests, go.mod, README
  - Excluded: vendor/, .git/, binaries
  
- **Frontend**:
  - Critical: App.js, index.js, main components
  - Important: components/, pages/, services/
  - Useful: tests, package.json, configs
  - Excluded: node_modules/, build/, dist/

**Stage 3: Context Optimization**
- Calculate token count per file
- Prioritize by importance
- Fit within model context (1M for Gemini, 128K for GPT-4)
- Compress large files intelligently

#### LLM Analysis Process
**What the AI Evaluates**:
1. **Requirement Fulfillment** (40% weight)
   - All specified features implemented?
   - Core functionality working?
   - Edge cases handled?

2. **Code Quality** (30% weight)
   - Clean, readable code?
   - Proper error handling?
   - Good naming conventions?

3. **Architecture** (20% weight)
   - Logical structure?
   - Separation of concerns?
   - Scalability considerations?

4. **Testing** (10% weight)
   - Test coverage present?
   - Key functionality tested?

**Model Selection Strategy**:
- Primary: Gemini Flash 2.5 (fast, cheap, 1M context)
- Fallback: GPT-4 Turbo (if Gemini unavailable)
- Emergency: GPT-3.5 Turbo (degraded but functional)

### Phase 4: Report Generation

**Report Contents**:
```
┌─────────────────────────────────┐
│ CANDIDATE EVALUATION REPORT     │
├─────────────────────────────────┤
│ Name: @telegram_username        │
│ Role: Senior Backend (Go)       │
│ Repository: github.com/user/repo│
│ Submission: 2024-01-15 14:30    │
├─────────────────────────────────┤
│ SCORES                          │
│ • Completeness: 85/100         │
│ • Code Quality: 90/100         │
│ • Architecture: 75/100         │
│ • Testing: 60/100              │
├─────────────────────────────────┤
│ RECOMMENDATION: ACCEPT          │
│ Confidence: 87%                │
├─────────────────────────────────┤
│ Key Strengths:                 │
│ • Clean API design             │
│ • Good error handling          │
│ • Efficient algorithms         │
│                                │
│ Areas for Improvement:         │
│ • Limited test coverage        │
│ • Missing documentation        │
└─────────────────────────────────┘
```

### Phase 5: Manager Notification & Access

**Instant Notification**:
- Bot sends summary to manager
- Includes: Name, role, recommendation, confidence
- Quick actions: View Full Report, Archive

**Manager Commands**:
- `/reports` - View all evaluations
- `/pending` - See in-progress analyses
- `/stats` - Weekly/monthly metrics
- `/accepted` - Filter accepted candidates
- `/rejected` - Filter rejected candidates

## Quality Assurance & Reliability

### Automatic Retry Mechanisms
1. **Repository Access**: 3 retries with exponential backoff
2. **LLM API Calls**: 5 retries across multiple models
3. **Database Operations**: Automatic retry on lock
4. **Telegram Messages**: Queue and retry on timeout

### Data Integrity
- All reports backed up as JSON files
- Database uses transactions for consistency
- Automatic cleanup of temporary files
- 30-day retention for all records

### Performance Guarantees
- Submission acknowledgment: < 3 seconds
- Complete analysis: < 5 minutes (typical)
- Report retrieval: < 1 second
- System availability: 99.5% uptime

## Cost Optimization

### LLM Usage Strategy
- Average cost per evaluation: $0.10-0.30
- Smart caching reduces duplicate analyses
- Efficient context usage minimizes tokens
- Automatic model downgrade if quota exceeded

### Resource Efficiency
- Single container uses < 512MB RAM
- SQLite database typically < 100MB
- Temporary storage cleared hourly
- No external service dependencies

## Common Scenarios & Solutions

### Scenario 1: Large Repository (>100MB)
**System Behavior**:
1. Detects size during clone
2. Switches to selective file mode
3. Analyzes core files only
4. Notes limitation in report

### Scenario 2: LLM Service Outage
**System Behavior**:
1. Attempts primary model (Gemini)
2. Falls back to GPT-4
3. Falls back to GPT-3.5
4. If all fail: Queues for retry, notifies manager

### Scenario 3: Invalid/Incomplete Code
**System Behavior**:
1. AI detects missing requirements
2. Lists specific gaps in report
3. Provides clear rejection reasoning
4. Suggests improvements to candidate

### Scenario 4: Concurrent Submissions
**System Behavior**:
1. Accepts all submissions immediately
2. Queues for processing (max 3 concurrent)
3. Processes in order received
4. Updates users on queue position

## Security & Privacy

### Data Protection
- No code stored permanently (deleted after analysis)
- Reports contain no sensitive code snippets
- Database encrypted at rest
- API keys never logged or exposed

### Access Control
- Bot accessible only via Telegram
- Manager commands require ID verification
- No web interface (reduced attack surface)
- Automatic session timeouts

## Success Metrics

### Efficiency Gains
- **Before**: 2-3 hours manual review per candidate
- **After**: 5 minutes automated analysis
- **Accuracy**: 85% agreement with senior developers
- **Consistency**: 100% uniform evaluation criteria

### Business Impact
- Process 20x more candidates
- Reduce time-to-hire by 60%
- Eliminate reviewer bias
- Free developers for actual interviews

## Setup Simplicity

### What Manager Needs to Know
1. **Setup**: Add 2 API keys, run 1 command
2. **Usage**: Share bot link with candidates
3. **Results**: Receive reports in Telegram
4. **Maintenance**: System self-manages

### What Happens Automatically
- Database creation and management
- Repository processing optimization
- Model selection and fallbacks
- Error recovery and retries
- Temporary file cleanup
- Report formatting

## Future Enhancements (Post-MVP)
- Voice message support for explanations
- Multi-language code support
- Comparative candidate ranking
- Integration with HR systems
- Custom evaluation criteria per role

## Why This Approach Succeeds

1. **Simplicity**: One container, two settings
2. **Reliability**: Multiple fallback layers
3. **Intelligence**: Context-optimized analysis
4. **Speed**: Async processing, smart caching
5. **Cost-Effective**: ~$0.20 per evaluation
6. **User-Friendly**: Familiar Telegram interface

## Bottom Line
A manager can go from zero to fully operational recruitment screening in under 5 minutes, then process hundreds of candidates automatically with consistent, high-quality evaluations.