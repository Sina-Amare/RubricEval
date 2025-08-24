# Senior Backend Developer (Go) - Technical Assessment

## Task Overview
Develop a backend service in Golang that implements OTP-based login and registration, along with basic user management features.

## Requirements

### 1. OTP Login & Registration
Implement OTP-based login and registration in Golang.

**Flow:**
- User sends phone number → system generates a random OTP
- OTP should be:
  - Printed to the console (no SMS sending required)
  - Stored temporarily (DB or in-memory)
  - Expire after 2 minutes
- User submits phone number + OTP:
  - If OTP is valid & not expired:
    - Register new user if not existing
    - Log in existing user otherwise
  - Upon success → return JWT token

### 2. Rate Limiting
Limit OTP requests:
- Max 3 requests per phone number within 10 minutes

### 3. User Management
REST endpoints for:
- Retrieve single user details
- Retrieve list of users with:
  - Pagination
  - Search (by phone number or other relevant fields)

User data must store at minimum:
- Phone number
- Registration date

### 4. Database
- Any database type allowed
- Must explain choice in documentation
- If using a DB:
  - Set up with docker-compose
- If not using a DB:
  - Use in-memory storage for simplicity

### 5. API Documentation
- All operations must be exposed via REST APIs
- Document with Swagger/OpenAPI

### 6. Architecture & Best Practices
- Use a clean, maintainable architecture (type not specified, but follow best practices)
- Ensure clear separation of responsibilities in code

### 7. Containerization
- Application must be Dockerized
- Include DB in docker-compose (if applicable)

### 8. Deliverables
- Source code
- Documentation:
  - How to run locally
  - How to run with Docker
  - Example API requests & responses
  - Database choice justification

## Time Limit
You have 48 hours to complete this task.

## Evaluation Criteria

Your submission will be evaluated based on:

1. **Functionality** (40%)
   - All features work as specified
   - OTP flow is correctly implemented
   - JWT authentication works properly
   - Rate limiting is effective

2. **Code Quality** (30%)
   - Clean, readable Go code
   - Proper error handling
   - Following Go idioms and best practices
   - Good project structure

3. **Architecture** (20%)
   - Separation of concerns
   - Scalable design
   - Proper use of interfaces
   - Database/storage design

4. **Documentation & DevOps** (10%)
   - Clear setup instructions
   - API documentation completeness
   - Docker configuration
   - Code comments where necessary