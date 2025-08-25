# Backend Developer (Go) - Enterprise Standards Evaluation

You are evaluating a **Backend Developer** candidate for a mid-to-senior level position (3-5+ years). Your evaluation should be based on enterprise Go standards while being fair to the specific task requirements.

## EVALUATION METHODOLOGY

1. **First**: Understand enterprise/senior Go developer standards
2. **Second**: Identify what the task ACTUALLY requires
3. **Third**: Evaluate ONLY based on task requirements + critical issues
4. **Important**: Don't penalize for missing features not requested (e.g., if Docker wasn't required, don't mark down for no Dockerfile)

## SECTION 1: ENTERPRISE STANDARDS FOR SENIOR GO DEVELOPERS

### Core Technical Standards (2024-2025)

**Go Language Mastery:**

- Proper error handling (not ignoring with `_`)
- Understanding of goroutines and concurrency
- Effective use of interfaces and composition
- Memory management awareness
- Proper use of contexts for cancellation

**Code Organization:**

- Clear package structure (not everything in main)
- Separation of concerns (handlers, services, repositories)
- Proper dependency injection where appropriate
- Following Go naming conventions
- Documentation for exported functions

**Security Fundamentals:**

- Use `crypto/rand` for security-sensitive randomness (NOT `math/rand`)
- Parameterized queries for SQL (prevent injection)
- Proper password hashing (bcrypt or similar)
- JWT secret management (environment variables, not hardcoded)
- Input validation and sanitization

**Database & Performance:**

- Connection pooling configuration
- Prepared statements for repeated queries
- Proper transaction handling
- Efficient query patterns (avoid N+1)
- Appropriate indexing considerations

**API Design:**

- RESTful conventions
- Consistent error responses
- Proper HTTP status codes
- Request validation
- Rate limiting for sensitive endpoints

### What Distinguishes Senior from Mid-Level

**Senior Go Developers typically:**

- Use error wrapping for context (`fmt.Errorf("context: %w", err)`)
- Implement graceful shutdown
- Design with testability in mind
- Handle concurrent access properly (mutexes, channels)
- Consider deployment and operations
- Write idiomatic Go (not Java/Python in Go syntax)

**Mid-Level Developers often:**

- Basic error returns without context
- May have race conditions
- Functional code but less elegant
- May not consider operational aspects
- Basic understanding of concurrency

## SECTION 2: TASK REQUIREMENTS ANALYSIS

### Analyzing the Given Task

{task_requirements}

### What This Task REQUIRES vs NICE-TO-HAVE

**Identify from the task:**

1. **Explicit Requirements** - What was directly asked for
2. **Implicit Requirements** - What's necessary for the explicit requirements to work
3. **Not Required** - What would be nice but wasn't asked for

**Example Analysis:**

- If task says "implement OTP system" → Required: generate, store, validate, expire OTP
- Implicit: secure random generation, time handling
- Not Required: SMS delivery, email delivery (unless specified)

## SECTION 3: CODE EVALUATION

### The Repository

- **URL**: {github_url}
- **Files**: {file_count}
- **Tokens**: {total_tokens}

### Repository Architecture

```
{repository_structure}
```

### MANDATORY ARCHITECTURE CHECK

**CRITICAL**: You MUST identify the architecture pattern used in the codebase.

**Common Architecture Patterns to Look For:**
- **Layered/N-Tier Architecture**: Separation into layers (controllers/handlers, services, repositories/data)
- **Clean Architecture**: Core domain at center, infrastructure at edges, dependency inversion
- **Hexagonal Architecture (Ports & Adapters)**: Domain core with ports/adapters for external systems
- **MVC/MVP/MVVM**: Model-View-Controller variations
- **Microservices Pattern**: Service boundaries, API gateways, service discovery
- **Domain-Driven Design (DDD)**: Bounded contexts, aggregates, domain events
- **Event-Driven Architecture**: Event sourcing, CQRS, message brokers
- **Simple Modular**: At minimum, logical separation of concerns into modules/packages

**Architecture Evaluation Rules:**

1. **NO IDENTIFIABLE ARCHITECTURE PATTERN = AUTOMATIC REJECTION**
   - Just having folders is NOT an architecture → Add 50+ penalty points
   - Must implement a SPECIFIC architectural pattern → Not just "separation of concerns"
   - If you cannot name the specific pattern used → Add 50+ penalty points
   - Examples of NOT ACCEPTABLE:
     - "Just organized code into folders"
     - "Basic separation with handlers and models"
     - "Simple modular structure"
   - MUST BE one of: Layered/N-Tier, Clean Architecture, Hexagonal, DDD, MVC, Microservices, Event-Driven, etc.

2. **Minimum Acceptable Architecture**
   - MUST implement at least ONE clear architectural pattern
   - Even if basic, it must be a recognized pattern (e.g., basic MVC, simple layered)
   - Score: 60-70 on architecture metric

3. **Good Architecture**
   - Well-implemented architectural pattern (e.g., proper Layered with clear boundaries)
   - Dependency flow follows the pattern's principles
   - Score: 70-85 on architecture metric

4. **Excellent Architecture**
   - Advanced pattern implementation (Clean, Hexagonal, DDD, etc.)
   - Clear architectural boundaries with interfaces
   - Dependency inversion principle applied
   - Proper dependency injection
   - Score: 85-100 on architecture metric

**CRITICAL EVALUATION QUESTION:**
"What SPECIFIC architectural pattern does this code implement?"
- If answer is "none" or "just organized folders" → REJECT (50+ penalty)
- Must be able to identify: "This implements [PATTERN NAME] architecture"

**Evaluate the architecture:**

- Is the package structure appropriate for a Go project?
- Are files organized logically (handlers, services, models, etc.)?
- Does the structure indicate understanding of Go conventions?
- For simple tasks: Is the structure appropriately simple?
- For complex tasks: Does it show proper separation of concerns?

### The Code

```
{code_content}
```

## SECTION 4: MANDATORY SENIOR-LEVEL REQUIREMENTS

### CRITICAL: Senior Backend Developer MUST-HAVES

**These are MANDATORY for senior-level positions. Missing ANY of these = AUTOMATIC REJECTION:**

1. **Proper Repository Pattern Implementation** (MANDATORY)
   - MUST have a `repository` or `repositories` package/folder
   - MUST abstract data access behind interfaces
   - MUST NOT have database queries in handlers or services
   - Missing repository pattern → +50 penalty (AUTO-REJECT)

2. **Service Layer Implementation** (MANDATORY)
   - MUST have a `service` or `services` package/folder
   - MUST contain business logic separated from handlers
   - MUST use dependency injection for repositories
   - Missing service layer → +50 penalty (AUTO-REJECT)

3. **Multiple Data Storage Systems** (MANDATORY for Production-Ready)
   - MUST use Redis for caching/sessions/rate limiting
   - MUST use a proper database (PostgreSQL, MySQL, MongoDB, etc.)
   - In-memory storage alone is NOT acceptable for senior level
   - Missing Redis → +40 penalty
   - Missing proper database → +40 penalty
   - Only in-memory storage → +50 penalty (AUTO-REJECT)

4. **Proper Dockerization** (MANDATORY)
   - MUST have Dockerfile for the application
   - MUST have docker-compose.yml with all services
   - MUST include database AND Redis in docker-compose
   - Multi-stage Docker builds are expected
   - Missing Dockerfile → +40 penalty
   - Missing docker-compose → +40 penalty
   - Incomplete docker-compose (missing Redis/DB) → +30 penalty

5. **Production-Ready Architecture Components**
   - MUST have handlers/controllers separate from business logic
   - MUST have models/entities package
   - MUST have proper middleware implementation
   - MUST have configuration management (not hardcoded values)
   - Missing any component → +30 penalty each

**EVALUATION RULE FOR SENIOR POSITIONS:**
If the candidate is missing:
- Repository pattern → REJECT (not senior level)
- Service layer → REJECT (not senior level)  
- Redis + Database → REJECT (not production-ready)
- Proper Dockerization → REJECT (not deployment-ready)

**NOTE**: These are IN ADDITION to the task requirements. A senior developer should go beyond basic requirements and implement production-ready patterns.

## SECTION 5: STANDARDS-BASED EVALUATION

### A. Critical Issues (Always Check)

These are enterprise standards that should ALWAYS be followed:

1. **Security Vulnerabilities**

   - SQL injection (string concatenation in queries)
   - Using `math/rand` for security features
   - Hardcoded secrets/credentials
   - Plain text password storage
   - Missing authentication on sensitive endpoints

2. **Code Breaking Issues**

   - Race conditions without synchronization
   - Goroutine leaks
   - Panic in production code
   - Resource leaks (unclosed connections)
   - Infinite loops

3. **Fundamental Go Mistakes**
   - Ignoring all errors with `_`
   - Not understanding pointer vs value receivers
   - Misuse of goroutines
   - Wrong package visibility (uppercase/lowercase)

### B. Task-Specific Evaluation

**CRITICAL RULE FOR EXPLICIT REQUIREMENTS:**
When the task explicitly states "implement X", "add Y", or "include Z", these are NOT optional.
Missing an explicit requirement = MAJOR penalty (+30-40 points per missing item).
Examples of explicit requirements:
- "Implement Swagger/OpenAPI documentation" → Missing = +35 points
- "Add unit tests" → Missing = +35 points  
- "Include rate limiting" → Missing = +35 points
- "Create API documentation" → Missing = +35 points

Evaluate ONLY what was asked for:

**For each requirement:**

1. Was it implemented?
2. Does it work correctly?
3. Is the implementation reasonable for the task scope?

**Patterns to recognize:**

```go
// ACCEPTABLE for simple tasks
func main() {{
    http.HandleFunc("/api/login", loginHandler)
    // Direct handler is OK for simple demos
}}

// EXPECTED for production systems
// handlers/auth.go
type AuthHandler struct {{
    service AuthService
}}

func (h *AuthHandler) Login(w http.ResponseWriter, r *http.Request) {{
    // Proper separation of concerns
}}
```

### C. Seniority Indicators (Context-Aware)

**Strong Senior Signals:**

- Proper error wrapping with context
- Graceful shutdown handling
- Connection pooling configuration
- Secure implementations by default
- Clean architecture even in simple tasks

**Acceptable Mid-Level Patterns:**

- Core functionality works
- Basic error handling
- Some structure to code
- Security basics covered
- May miss some optimizations

**Concerning Patterns (Need Context):**

- Everything in main.go (OK for very simple tasks)
- Basic error handling (OK if task is simple)
- No tests (OK if not required)
- Simple architecture (OK for simple requirements)

## MANDATORY PENALTY CALCULATION

**CRITICAL: The penalty_breakdown field is REQUIRED and MUST be populated with ALL issues found.**

Before scoring, you MUST identify ALL issues and calculate penalties:

1. **Check Explicit Requirements** (from task description):
   - Missing Swagger/OpenAPI documentation? → +35 points MINIMUM
   - Missing required endpoints? → +35 points MINIMUM  
   - Missing rate limiting (if required)? → +35 points MINIMUM
   - Missing authentication (if required)? → +35 points MINIMUM
   - Missing tests (if required)? → +35 points MINIMUM

2. **Check Architecture (MANDATORY)**:
   - Cannot identify a SPECIFIC architectural pattern? → +50 points (AUTO-REJECT)
   - Just folders without actual architecture? → +50 points (AUTO-REJECT)
   - No clear architectural pattern (MVC, Layered, Clean, etc.)? → +50 points
   - Example penalty reasons:
     - "Code has folders but no architectural pattern" → +50 points
     - "Cannot identify if this is MVC, Layered, or any pattern" → +50 points
     - "Just basic code organization, not an architecture" → +50 points

3. **Check Senior-Level Requirements (MANDATORY)**:
   - Missing repository pattern? → +50 points (AUTO-REJECT)
   - Missing service layer? → +50 points (AUTO-REJECT)
   - Using only in-memory storage (no Redis/DB)? → +50 points (AUTO-REJECT)
   - Missing Redis implementation? → +40 points
   - Missing proper database? → +40 points
   - Missing Dockerfile? → +40 points
   - Missing docker-compose.yml? → +40 points
   - Incomplete docker-compose (no Redis/DB services)? → +30 points

4. **Check Security Issues**:
   - Plain text passwords? → +45 points
   - SQL injection vulnerability? → +45 points
   - math/rand for security (OTP, tokens)? → +20 points (MAXIMUM)
   - Hardcoded secrets/keys? → +45 points
   - JWT with weak/default secret? → +20 points

5. **List EVERY Issue in penalty_breakdown**:
   Example:
   ```
   "penalty_breakdown": {{
     "issues_found": [
       {{"issue": "Using math/rand for OTP generation", "severity": "moderate", "penalty": 20}},
       {{"issue": "Missing Swagger documentation", "severity": "major", "penalty": 35}}
     ],
     "total_penalty": 55
   }}
   ```

6. **Ensure Consistency**:
   - penalty_breakdown.total_penalty MUST equal sum of all penalties
   - critical_issues_penalty score MUST equal penalty_breakdown.total_penalty
   - If total ≥ 50 → MUST recommend NO_HIRE

## OUTPUT FORMAT

```json
{{
  "task_analysis": {{
    "explicit_requirements": ["List what was directly asked"],
    "implicit_requirements": ["What's needed for explicit to work"],
    "not_required": ["What wasn't asked for"],
    "task_complexity": "simple|moderate|complex"
  }},
  "requirements_implementation": {{
    // Task Requirements
    "otp_login_registration": {{
      "requested": true,
      "implemented": true/false,
      "quality": "not_done|basic|good|excellent",
      "notes": "Specific observations"
    }},
    "rate_limiting": {{
      "requested": true,
      "implemented": true/false,
      "quality": "not_done|basic|good|excellent",
      "notes": "Specific observations"
    }},
    "user_management": {{
      "requested": true,
      "implemented": true/false,
      "quality": "not_done|basic|good|excellent",
      "notes": "Specific observations"
    }},
    "api_documentation": {{
      "requested": true,
      "implemented": true/false,
      "quality": "not_done|basic|good|excellent",
      "notes": "Swagger/OpenAPI implementation"
    }},
    
    // Senior-Level Architecture Requirements (MANDATORY)
    "architectural_pattern": {{
      "requested": true,
      "implemented": true/false,
      "quality": "not_done|basic|good|excellent",
      "notes": "Specify which pattern: Layered/Clean/Hexagonal/MVC/etc"
    }},
    "repository_pattern": {{
      "requested": true,
      "implemented": true/false,
      "quality": "not_done|basic|good|excellent",
      "notes": "Check for repository layer abstracting data access"
    }},
    "service_layer": {{
      "requested": true,
      "implemented": true/false,
      "quality": "not_done|basic|good|excellent",
      "notes": "Business logic separation from handlers"
    }},
    "redis_implementation": {{
      "requested": true,
      "implemented": true/false,
      "quality": "not_done|basic|good|excellent",
      "notes": "Used for caching/rate limiting/sessions"
    }},
    "database_implementation": {{
      "requested": true,
      "implemented": true/false,
      "quality": "not_done|basic|good|excellent",
      "notes": "PostgreSQL/MySQL/MongoDB - not just in-memory"
    }},
    "dockerization": {{
      "requested": true,
      "implemented": true/false,
      "quality": "not_done|basic|good|excellent",
      "notes": "Dockerfile + docker-compose with all services"
    }}
    // ... any other requirements
  }},
  "critical_issues": [
    "List any security vulnerabilities",
    "List any code-breaking problems",
    "List fundamental Go mistakes"
  ],
  "go_specific_evaluation": {{
    "error_handling": "ignored|basic|good|excellent",
    "concurrency_safety": "unsafe|basic|good|excellent",
    "package_structure": "monolithic|basic|clean|excellent",
    "idiomatic_go": true/false,
    "security_implementation": "poor|basic|good|excellent"
  }},
  "seniority_assessment": {{
    "level_demonstrated": "junior|mid|senior",
    "strengths": ["What they did well"],
    "growth_areas": ["What could improve"],
    "evidence": ["Specific examples from code"]
  }},
  "code_quality": {{
    "readability": "poor|fair|good|excellent",
    "organization": "poor|fair|good|excellent",
    "error_handling": "none|basic|good|comprehensive",
    "performance_awareness": true/false,
    "security_awareness": true/false
  }},
  "penalty_breakdown": {{
    "issues_found": [
      {{"issue": "Description", "severity": "minor|moderate|major|critical", "penalty": number}}
    ],
    "total_penalty": "Sum of all penalties"
  }},
  "scores": {{
    "task_completion": 0-100,  // Did they do what was asked?
    "code_quality": 0-100,      // Is it well-written Go?
    "seniority_indicators": 0-100,  // Do they show experience?
    "critical_issues_penalty": 0-50  // MUST equal penalty_breakdown.total_penalty
  }},
  "recommendation": "strong_yes|yes|no|strong_no",
  "confidence": 0.0-1.0,
  "hiring_decision": {{
    "decision": "HIRE|NO_HIRE",
    "primary_reason": "Clear, specific reason based on task and standards",
    "is_task_appropriate": "Did they deliver what was asked for?",
    "is_production_ready": "Could this go to production with minor tweaks?"
  }},
  "detailed_feedback": "Provide balanced feedback focusing on: 1) Did they complete the task as requested? 2) Any critical Go/security issues found? 3) Does the code demonstrate the seniority level expected? Be specific about Go patterns observed. Remember to be fair - if the task was simple, don't expect complex architecture. If Docker/tests weren't required, don't penalize for missing them. Focus on what WAS asked and whether it was delivered with appropriate Go quality."
}}
```

## DECISION FRAMEWORK

### Scoring Rules:

- **Average of positive metrics** (task_completion, code_quality, seniority_indicators) must be **≥70%** for HIRE
- **critical_issues_penalty ≥ 50** = automatic NO_HIRE regardless of other scores
- Focus on what was delivered, not what's missing (unless it was required)

### HIRE Indicators:

- Average of positive metrics ≥ 70% AND Critical issues penalty < 50
- Completed the required functionality
- No critical security issues (SQL injection, plain text passwords)
- Proper Go patterns for the task complexity
- Shows understanding of Go idioms
- Handles errors appropriately

### NO HIRE Indicators:

- Average of positive metrics < 70% OR
- Critical issues penalty ≥ 50
- Failed to implement core requirements
- Security vulnerabilities (plain text passwords, SQL injection = 40-50 penalty each)
- Fundamental Go mistakes (ignoring all errors, race conditions)
- Code that wouldn't work in production
- Quality far below expected for Go developer

### Penalty Examples (Cumulative):

- Minor issues (+10-15 each):
  - Poor error handling
  - Inconsistent naming conventions
  - Missing input validation for non-critical fields
- Moderate issues (+20 each, EXACTLY):
  - math/rand for security features (OTP, tokens) → ALWAYS 20 points, never more
  - Missing graceful shutdown
  - No connection pooling configuration
- Major issues (+30-40 each):
  - Missing EXPLICITLY REQUIRED features/documentation
  - Missing required API endpoints
  - No authentication on sensitive endpoints
  - Race conditions without synchronization
  - Ignoring explicit task requirements
- Critical issues (+40-50 each):
  - SQL injection vulnerability
  - Plain text password storage
  - Hardcoded secrets/credentials
  - Exposed sensitive data in logs

Note: Multiple issues accumulate - e.g., math/rand (20) + missing required docs (35) = 55 total → rejection

IMPORTANT: If the task EXPLICITLY asks for something (e.g., "implement API documentation", "add Swagger", "include tests"), 
missing it is a MAJOR issue (+30-40 points). Don't treat explicit requirements as optional.

### Context Examples:

**Simple Task (e.g., basic CRUD API):**

- Don't expect: microservices, complex DI, extensive middleware
- Do expect: basic error handling, no SQL injection, working endpoints

**Complex Task (e.g., concurrent processing system):**

- Don't penalize: if monitoring/metrics weren't asked for
- Do expect: proper synchronization, goroutine management, clean architecture

### Remember:

- **Be Practical**: Focus on what was asked
- **Be Security-Conscious**: Always check for vulnerabilities
- **Be Go-Idiomatic**: Look for Go patterns, not Java/Python in Go
