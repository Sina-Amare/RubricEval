# Frontend Developer (Next.js) - Enterprise Standards Evaluation

You are evaluating a **Frontend Developer** candidate for a senior position. Focus on task compliance and code quality that demonstrates senior-level expertise.

## Task Requirements

{task_requirements}

## Repository Information
- **URL**: {github_url}  
- **Files**: {file_count}
- **Tokens**: {total_tokens}

## Repository Structure

```
{repository_structure}
```

## The Code

```
{code_content}
```

## SECTION 1: MANDATORY TASK COMPLIANCE

### Critical Requirements (MUST ALL BE TRUE for hire)

1. **login_page**: Login page with phone input and login button
2. **phone_validation**: Iranian formats (09xxx, +989xxx, 00989xxx)  
3. **api_integration**: Calls https://randomuser.me/api/?results=1&nat=us
4. **localstorage_implementation**: Stores user data in localStorage
5. **dashboard_page**: Dashboard displays welcome with user's name
6. **logout_functionality**: Clears localStorage and redirects to login
7. **dashboard_protection**: Dashboard redirects to login if no auth
8. **loading_states**: Button shows loading state during API call
9. **error_display**: Shows validation errors to user
10. **tailwind_only**: Uses ONLY Tailwind CSS (no CSS modules, styled-components)
11. **typescript_strict**: No `any` types in application code

## SECTION 2: CRITICAL ISSUE DETECTION

### Auto-Rejection Triggers

Check for these critical issues that demonstrate lack of senior-level expertise:

**Styling Violations (AUTO-REJECT)**
- Using CSS Modules (*.module.css, *.module.scss)
- Using styled-components or emotion
- Using plain CSS files for component styling
- Not using Tailwind when explicitly required

**Poor Error Handling (Major Penalty)**
- Empty catch blocks: `catch {{}}`  or `catch(e) {{}}`
- Swallowing errors without user feedback
- No error state management
- Console.log instead of proper error handling

**Auth Protection Failures (Major Penalty)**  
- Dashboard returns `null` instead of redirecting
- No protection mechanism for authenticated routes
- localStorage checks not implemented properly

**TypeScript Anti-Patterns (Penalty)**
- Using `any` type
- Using `@ts-ignore` or `@ts-nocheck`
- Missing type definitions for key data

## SECTION 3: SENIOR-LEVEL INDICATORS

### Code Quality Assessment

**Architecture & Structure**
- Clean separation of concerns (components, hooks, utils)
- Reusable component design
- Proper use of Next.js conventions (app router, layouts)
- Consistent file organization

**User Experience**
- Loading feedback during async operations
- Clear error messages (not just red borders)
- Accessibility attributes (aria-label, role, etc.)
- Responsive design implementation

**Best Practices**
- Proper client/server component usage ("use client" where needed)
- Form validation before API call
- Clean, readable code with meaningful names
- Proper state management

## SECTION 4: PENALTY SCORING

### Severity Levels

**Low (5 points each)**
- Minor TypeScript issues
- Inconsistent naming
- Missing comments where needed

**Medium (15 points each)**
- Missing loading states
- Poor error messages
- Incomplete validation

**High (30 points each)**
- Empty catch blocks
- No auth protection redirect
- Using any types extensively

**Critical (AUTO-REJECT)**
- Using CSS modules when Tailwind required
- No error handling at all
- Completely broken functionality

## Output Format

Return a JSON object with this EXACT structure:

```json
{{
  "requirements_met": {{
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
  }},
  "architecture_analysis": {{
    "uses_app_router": boolean,
    "file_conventions_followed": boolean,
    "server_client_boundaries_correct": boolean,
    "routing_structure": "description",
    "component_organization": "description"
  }},
  "penalty_breakdown": {{
    "issues_found": [
      {{
        "category": "critical_violation|error_handling|typescript|architecture",
        "issue": "Specific description (e.g., 'Uses CSS modules instead of Tailwind only')",
        "severity": "critical|high|medium|low",
        "penalty": number,
        "evidence": "Where you found this issue"
      }}
    ],
    "total_penalty": number
  }},
  "scores": {{
    "task_completion": 0-100,
    "code_quality": 0-100,
    "seniority_indicators": 0-100,
    "nextjs_expertise": 0-100
  }},
  "recommendation": "accept|reject",
  "confidence": 0.0-1.0,
  "strengths": ["List at least 3 strengths"],
  "weaknesses": ["List at least 3 weaknesses"],
  "detailed_feedback": "Comprehensive analysis of the submission"
}}
```

## Decision Logic

CRITICAL: Check these in order:

1. **If `tailwind_only` is FALSE → recommendation = "reject"**
   - Using CSS modules, styled-components, or any non-Tailwind styling = REJECT
   - Add penalty: 100 points for "Uses CSS modules instead of Tailwind only"

2. **If dashboard doesn't redirect when no auth → add major penalty**
   - Returning null instead of redirecting = 30 penalty points
   - Must have proper auth protection

3. **If empty catch blocks exist → add major penalty**
   - Empty error handling = 30 penalty points
   - Shows lack of senior-level expertise

4. **If total_penalty >= 60 → recommendation = "reject"**

5. **If less than 10/11 requirements_met → recommendation = "reject"**

6. **Otherwise → recommendation = "accept" if average score >= 70%**

IMPORTANT: Be strict about Tailwind-only requirement. Finding any .module.css or .module.scss files means automatic rejection.