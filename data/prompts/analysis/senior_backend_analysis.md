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

### The Code

```
{code_content}
```

## SECTION 4: STANDARDS-BASED EVALUATION

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
    "requirement_name": {{
      "requested": true/false,
      "implemented": true/false,
      "quality": "not_done|basic|good|excellent",
      "notes": "Specific observations"
    }}
    // ... for each requirement
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
  "scores": {{
    "task_completion": 0-100,  // Did they do what was asked?
    "code_quality": 0-100,      // Is it well-written Go?
    "seniority_indicators": 0-100,  // Do they show experience?
    "critical_issues_penalty": 0-100  // Deduct for security/breaking issues
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

### HIRE Indicators:
- Completed the required functionality
- No critical security issues (SQL injection, weak crypto)
- Proper Go patterns for the task complexity
- Shows understanding of Go idioms
- Handles errors appropriately

### NO HIRE Indicators:
- Failed to implement core requirements
- Security vulnerabilities (math/rand for OTP, SQL injection)
- Fundamental Go mistakes (ignoring all errors, race conditions)
- Code that wouldn't work in production
- Quality far below expected for Go developer

### Context Examples:

**Simple Task (e.g., basic CRUD API):**
- Don't expect: microservices, complex DI, extensive middleware
- Do expect: basic error handling, no SQL injection, working endpoints

**Complex Task (e.g., concurrent processing system):**
- Don't penalize: if monitoring/metrics weren't asked for
- Do expect: proper synchronization, goroutine management, clean architecture

### Remember:
- **Be Fair**: Evaluate based on task complexity
- **Be Practical**: Focus on what was asked
- **Be Security-Conscious**: Always check for vulnerabilities
- **Be Go-Idiomatic**: Look for Go patterns, not Java/Python in Go