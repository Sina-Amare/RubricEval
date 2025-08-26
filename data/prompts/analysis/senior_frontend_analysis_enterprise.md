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

## SECTION 2: NEXT.JS APP ROUTER BEST PRACTICES

### Required Implementation Standards

**1. App Router File Conventions**
- `page.tsx` for route pages (not `index.tsx`)
- `layout.tsx` for layouts (required for proper routing)
- `loading.tsx` for loading states (optional but recommended)
- `error.tsx` for error boundaries (optional but recommended)
- Route groups with `(folderName)` for organization without URL impact
- Dynamic routes with `[param]` folders
- Proper use of `"use client"` directive only where needed

**2. Client vs Server Components**
- Server Components by default (no "use client" unless needed)
- "use client" ONLY for:
  - Interactive elements (onClick, onChange, etc.)
  - Browser APIs (localStorage, window, document)
  - React hooks (useState, useEffect, etc.)
  - Third-party client-only libraries
- Data fetching should happen in Server Components when possible
- Form actions can use Server Actions (preferred over API routes for mutations)

**3. Next.js Navigation Best Practices**
- Use `useRouter` from `next/navigation` (NOT `next/router`)
- Use `Link` from `next/link` for client-side navigation
- Use `redirect()` from `next/navigation` ONLY in Server Components/Actions
- For client-side navigation in event handlers: `router.push()` or `router.replace()`
- Never use `window.location.href` for internal navigation

**4. Data Management & State**
- localStorage/sessionStorage access ONLY in client components
- Wrap localStorage access in useEffect or check `typeof window !== 'undefined'`
- Use proper loading states during async operations
- Handle errors gracefully with try-catch and user feedback

**5. TypeScript Best Practices**
- Define interfaces/types for all data structures
- No `any` type usage (use `unknown` if type is truly unknown)
- Proper type inference from API responses
- Type safety for route params and search params

**6. Tailwind CSS Implementation**
- Use Tailwind utility classes exclusively
- No inline styles unless absolutely necessary
- Responsive design with Tailwind breakpoints (sm:, md:, lg:, xl:)
- Consistent spacing using Tailwind's spacing scale
- Dark mode support with dark: variants (if applicable)

**7. Performance Optimizations**
- Images using next/image component with proper sizing
- Fonts using next/font for optimization
- Code splitting happens automatically with app router
- Lazy loading for heavy client components

## SECTION 3: CRITICAL ISSUE DETECTION

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

**IMPORTANT**: Be fair and reasonable with penalties. The goal is to identify serious issues, not accumulate minor infractions. A working solution with minor issues should still be accepted if it meets core requirements.

### Severity Levels

**Low (5 points each)**
- Minor TypeScript issues
- Inconsistent naming
- Missing comments where needed

**Medium (10 points each)**
- Missing loading states
- Poor error messages
- TypeScript type issues (not any)
- Minor auth protection issues

**High (15 points each)**
- Using redirect() in client component (but works)
- Missing error handlers for API calls
- Incomplete validation (some formats missing)
- Dashboard returns null instead of redirecting

**Very High (25-30 points each)**
- Empty catch blocks: 30 points
- Using any types extensively: 25 points
- No auth protection at all: 25 points

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
  "detailed_feedback": "Comprehensive analysis of the submission",
  "candidate_explanation": "REQUIRED FIELD - MUST NOT BE EMPTY. A professional, constructive explanation for the candidate about why their submission was accepted or rejected. This should be educational and help them understand the decision. Be specific about what they did well and what needs improvement. If rejected, provide actionable feedback on how to meet senior-level standards. Write 4-6 sentences that the candidate will find helpful and encouraging. DO NOT leave this field empty or undefined."
}}
```

## Decision Logic

CRITICAL: Check these in order:

1. **If `tailwind_only` is FALSE → recommendation = "reject"**
   - Using CSS modules, styled-components, or any non-Tailwind styling = REJECT
   - Add penalty: 100 points for "Uses CSS modules instead of Tailwind only"

2. **If empty catch blocks exist → add major penalty**
   - Empty error handling = 30 penalty points
   - Shows lack of senior-level expertise

3. **Calculate total penalty carefully**
   - Sum all penalties but be fair about severity
   - Minor issues that still work shouldn't accumulate to rejection

4. **If total_penalty >= 60 → recommendation = "reject"**

5. **If less than 9/11 requirements_met → recommendation = "reject"**
   - Must have at least 9 out of 11 requirements to be considered

6. **Otherwise → recommendation = "accept"**
   - If penalty < 60 AND requirements >= 9/11 → ACCEPT
   - Focus on core functionality over perfect implementation
   - Consider that redirect() in client component still works even if not best practice

IMPORTANT: Be strict about Tailwind-only requirement. Finding any .module.css or .module.scss files means automatic rejection.

## Candidate Explanation Guidelines

**⚠️ CRITICAL: The `candidate_explanation` field is MANDATORY and MUST be filled with a thoughtful, personalized message.**

When writing the `candidate_explanation` field:

1. **For ACCEPTED candidates**: 
   - Start with congratulations
   - Highlight 2-3 specific technical strengths you observed
   - Mention how their code demonstrates senior-level expertise
   - Note any minor areas for future improvement
   - End with next steps

2. **For REJECTED candidates**:
   - Be respectful and constructive
   - Clearly state which mandatory requirements were not met
   - Acknowledge what they did well
   - Provide specific, actionable feedback for improvement
   - Encourage them to reapply after addressing the issues

3. **Tone and Language**:
   - Professional and encouraging
   - Specific examples from their code
   - Avoid generic statements
   - Focus on technical skills, not personal criticism
   - Educational approach to help growth

### Example Candidate Explanations:

**For ACCEPTED submission:**
"Congratulations on your excellent submission! Your implementation demonstrates strong proficiency in Next.js App Router, with particularly impressive component organization using the molecules/organisms pattern. The Tailwind CSS implementation is clean and responsive, and your form validation logic is robust. While we noted minor issues with the redirect() usage in client components (consider using router.push() instead), these don't detract from the overall quality. Your code meets our senior-level standards, and we're excited to move forward with your application."

**For REJECTED submission:**
"Thank you for your submission. Your code shows good understanding of React and component structure, which are valuable skills. However, the requirement specifically called for Tailwind CSS only, and your use of CSS modules unfortunately disqualifies this submission. Additionally, the empty catch blocks in your error handling and missing TypeScript strict mode indicate areas needing improvement for senior-level positions. We encourage you to review these specific requirements carefully and resubmit once addressed. Your foundational skills are strong, and with these adjustments, you'd be a strong candidate."