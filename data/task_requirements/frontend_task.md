# Senior Frontend Developer - Technical Assessment

## 🧾 Task: Build an Authentication Page and Redirect to Dashboard (Next.js + TypeScript + SCSS Modules)

## 🎯 Objective
Implement a simple responsive authentication flow with two pages:
- `/auth` → Login page
- `/dashboard` → Dashboard page with a welcome message

## 📌 Overview
You are required to create a simple login page. When the user clicks the "Login" button, the app should:
- Send a GET request to: `https://randomuser.me/api/?results=1&nat=us`
- Store the user data (in localStorage or via Context API)
- Redirect the user to the dashboard page

Custom reusable components must be created for input and button elements.

## 📂 Pages & Routes
- `/auth` → Login form
- `/dashboard` → Simple page with a welcome message

## 🛠 Tech Stack
- Next.js (App Router)
- TypeScript
- SCSS Modules (with nesting support)

## 📋 Technical Requirements

### ✅ /auth Page:
- Includes a phone number input field for Iranian mobile numbers (for validation practice only, does not affect login)
  - Must validate: 11-digit number starting with "09"
- Includes a "Login" button
- On button click:
  - Fetch user from `https://randomuser.me/api/?results=1&nat=us`
  - Store user data in localStorage or Context (if using SSR)
  - Redirect to `/dashboard`
- Form must include validation (preferably schema-based, not inline)

### ✅ /dashboard Page:
- Displays a welcome message like "Welcome to the Dashboard"
- If no user data exists (e.g., localStorage is empty), the user should be redirected to `/auth`

## 🎨 Styling
- Use SCSS Modules (`.module.scss`)
- Utilize proper nesting for CSS class selectors

## ⚙️ Additional Front-End Requirements
- React can be used freely
- Use `forwardRef` where applicable (e.g., for controlled inputs)
- Use React Hooks for auth logic and state management
- Ensure high-level TypeScript safety with proper types or interfaces
- Build reusable components — no duplicated UI logic
- Codebase must be scalable and maintainable
- Apply proper naming conventions and folder structures
- Form validation must be dynamic and decoupled from input components (e.g., using a schema like Zod or Yup)

## ⏰ Deadline
Please complete the task within 48 hours after receiving it.

## Evaluation Criteria

Your submission will be evaluated based on:

1. **Functionality** (40%)
   - Authentication flow works correctly
   - Phone number validation is accurate
   - User data is properly stored and retrieved
   - Redirects work as expected

2. **Code Quality** (30%)
   - Clean, maintainable TypeScript code
   - Proper use of React patterns and hooks
   - Reusable component architecture
   - Schema-based validation implementation

3. **UI/UX & Styling** (20%)
   - Responsive design
   - Proper SCSS module usage with nesting
   - Clean and intuitive interface
   - Proper error handling and user feedback

4. **Best Practices** (10%)
   - TypeScript type safety
   - Proper folder structure
   - Use of forwardRef where appropriate
   - Scalable architecture