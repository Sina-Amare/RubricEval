# Project Brief: Automated Recruitment Screening System

## 1. Current Process & Needs

**Objective**: Streamline the technical screening process for Senior Backend (Go) and Senior Frontend positions.

**Current Workflow**:

- Applicants receive a take-home programming task.
- Applicants complete the task and push their solution to a public GitHub repository.
- Applicants submit the repository URL via Telegram.
- The team manually reviews the code and decides to accept or reject the candidate.

**Identified Need**: The manual process is time-consuming and prone to inconsistent reviews. An automated system is required to manage submissions and provide data-driven analysis.

## 2. Proposed Solution: Automated Screening Bot

A Telegram bot will be developed to automate the initial stages of the hiring pipeline.

**System Workflow**:

1. **Submission**: The Telegram bot receives GitHub repository URLs from applicants.
2. **Categorization**: The bot prompts the applicant to specify the role (Frontend or Backend).
3. **Analysis Trigger**: The submission enters a "reviewing" state, triggering backend analysis.
4. **Code Retrieval & Analysis**: The system fetches the repository's code and sends it, along with the task description, to a Large Language Model (LLM) for review. The analysis evaluates task requirement fulfillment and implementation quality.
5. **Report Generation**: The LLM generates a report including:
   - A thorough code review.
   - An assessment of performance against task requirements.
   - A final recommendation (Accept/Reject) with evidence from the codebase.
6. **Delivery & Storage**: The report is saved to local storage and delivered to the hiring manager via the Telegram bot.
7. **Manager Access**: The bot provides an interface for managers to view previous reports, with filters for "Accepted" and "Rejected" candidates.

## 3. Key Challenges & Considerations

- **LLM Context Limitation**: Develop a strategy to provide the LLM with full repository context without exceeding token limits. Initial plan: clone the repo and concatenate relevant source files.
- **System Robustness**: Ensure reliability with fallback mechanisms to handle failures (e.g., API downtime, invalid repository links).

## 4. Testing and Quality Assurance

A continuous testing strategy will ensure reliability and quality.

- **Manual Testing**: Regular end-to-end tests of Telegram bot interactions for applicants and managers to ensure an intuitive, bug-free user experience.
- **Automated Testing (Scripts)**: Develop scripts for:
  - Unit tests for individual functions.
  - Integration tests to verify communication with external APIs (GitHub, LLM) and proper data handling.

This dual approach will catch issues early, validate functionality, and ensure system stability.

## 5. Guiding Principles

### A. Decision Framework: Simplicity vs. Complexity

- **Start Simple**: Begin with the simplest approach that solves the problem.
- **Evaluate**: Assess if the solution meets requirements, avoids technical debt, and is easy to debug and extend.
- **Escalate if Necessary**: Only consider more complex solutions if the simple approach fails, choosing the least complex option that meets all needs.
- **Key Evaluation Criteria**: Implementation effort, long-term maintainability, debugging complexity, future extensibility, and team understanding.

### B. Critical Thinking and Alternative Approach Rule

- **When to Disagree**: Voice concerns if a more efficient/secure solution exists, significant flaws or risks are identified, or the approach contradicts industry best practices.
- **How to Disagree Constructively**: Acknowledge the current approach, explain problems, propose concrete alternatives with benefits, and provide reasoning based on technical merit.
- **Our Responsibility**: Build the best possible solution by considering edge cases, scalability, and long-term consequences.
