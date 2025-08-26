# Frontend Developer - Next.js Application Evaluation

You are evaluating a Frontend Developer candidate for a senior position. Evaluate based on the task requirements and code quality standards.

## Repository Information
- **URL**: {github_url}
- **Files**: {file_count}
- **Tokens**: {total_tokens}

## Repository Structure
```
{repository_structure}
```

## Task Requirements
{task_requirements}

## Repository Files

**CRITICAL INSTRUCTIONS FOR FILE REFERENCES**:
1. **ONLY reference files that appear in the code below** - DO NOT invent or assume files exist
2. **Copy file paths EXACTLY as shown** - including 'src/' prefix and parentheses like '(auth)' or '(dashboard)'
3. **If a file doesn't exist in the list below, mark the requirement as FALSE**
4. **DO NOT hallucinate files** - if you reference "src/app/(auth)/login/page.tsx" but it's not in the files below, you're wrong
5. **Common mistake**: If you only see "src/app/(dashboard)/page.tsx", don't reference "src/app/(dashboard)/dashboard/page.tsx"

**ACTUAL FILES IN THIS REPOSITORY**:
```
{code_content}
```

**REMEMBER**: Only use file paths that actually appear above. If localStorage is used in a file that doesn't exist, it means localStorage is NOT implemented.

## Evaluation Instructions

1. **FIRST**: Look at the actual files provided above - memorize what files exist
2. **Analyze ONLY the code provided** - not what you think should exist
3. **Use EXACT file paths** from the Repository Files section - no variations
4. **If a requirement needs a file that doesn't exist, mark it FALSE**
5. **Provide evidence ONLY from files that actually exist above**
6. **Example**: If you don't see "src/app/(auth)/login/page.tsx" in the files, DON'T reference it

**VALIDATION CHECK**: Before returning your response, verify every file path you reference exists in the Repository Files section above.

## Mandatory Requirements (All must be TRUE for hire)

1. **login_page_implementation**: Login/auth page with form
2. **phone_validation**: Iranian phone number validation (09xxx, +989xxx, 00989xxx)
3. **api_integration**: Fetch from https://randomuser.me/api/?results=1&nat=us
4. **localstorage_implementation**: User data stored in localStorage (check for localStorage.setItem)
5. **dashboard_page**: Dashboard showing user data
6. **logout_functionality**: Logout that clears storage
7. **nextjs_app_router**: Using App Router (app/ directory, not pages/)
8. **typescript_strict**: TypeScript with strict mode
9. **tailwind_only**: Tailwind CSS for styling
10. **responsive_design**: Mobile-responsive implementation
11. **folder_structure**: Organized with components/ and lib/ directories

## Penalty Guidelines

### Low (5 points each)
- Each `any` type usage (max 15 total)
- Direct DOM manipulation
- Poor naming conventions

### Medium (10-15 points)
- No loading states: 10 points
- No error handling for API: 15 points
- Poor code organization: 15 points

### High (20+ points)
- jQuery usage: 20 points
- Security vulnerabilities: 20 points
- No modular structure: 20 points

**Auto-rejection at 50+ penalty points**

## Critical Evidence Rules

**NEVER HALLUCINATE CODE OR LINE NUMBERS**:
1. Only reference code that you can literally see in the Repository Files section
2. Only use line numbers if they're shown in the file content
3. If you can't find localStorage code, mark it as FALSE - don't make up evidence
4. If a file exists but doesn't contain the expected code, that means the requirement is NOT met
5. Example: If login/page.tsx exists but has no localStorage.setItem, then localStorage is NOT implemented

## Output Format

Return a JSON object with this structure:

```json
{
  "storage_method_check": {
    "found_localStorage": boolean,
    "found_cookies": boolean,
    "found_sessionStorage": boolean,
    "storage_details": "Description of what you found",
    "evidence": "Exact line of code with file:line reference"
  },
  "requirements_met": {
    "login_page_implementation": boolean,
    "phone_validation": boolean,
    "api_integration": boolean,
    "localstorage_implementation": boolean,
    "dashboard_page": boolean,
    "logout_functionality": boolean,
    "nextjs_app_router": boolean,
    "typescript_strict": boolean,
    "tailwind_only": boolean,
    "responsive_design": boolean,
    "folder_structure": boolean
  },
  "architecture_analysis": {
    "uses_app_router": boolean,
    "file_conventions_followed": boolean,
    "server_client_boundaries_correct": boolean,
    "routing_structure": "description",
    "component_organization": "description"
  },
  "penalty_breakdown": {
    "issues_found": [
      {
        "category": "typescript|architecture|security|performance",
        "issue": "Description with exact file:line",
        "severity": "low|medium|high",
        "penalty": number,
        "evidence": "Code snippet from actual file"
      }
    ],
    "total_penalty": number
  },
  "scores": {
    "task_completion": 0-100,
    "code_quality": 0-100,
    "seniority_indicators": 0-100,
    "nextjs_expertise": 0-100,
    "critical_issues_penalty": number
  },
  "recommendation": "yes|no",
  "confidence": 0.0-1.0,
  "strengths": ["List of strengths found"],
  "weaknesses": ["List of weaknesses found"],
  "detailed_feedback": "Comprehensive feedback with specific file:line references"
}
```

## Decision Logic

1. If ANY of the 11 mandatory requirements is FALSE → recommendation = "no"
2. If total_penalty >= 50 → recommendation = "no"
3. If all requirements met AND penalty < 50 → evaluate quality scores
4. If average quality score >= 70% → recommendation = "yes"
5. Otherwise → recommendation = "no"

Focus on finding real issues in the actual code, not theoretical improvements.