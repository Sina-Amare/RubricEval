# Frontend Developer - Technical Assessment

## 🚀 Goal

Implement a login flow with two pages:
- 📱 Login page with mobile number input (Iran format only) + "Login" button
- 🏠 Dashboard page that welcomes the user

## 📋 Details

### 🔑 Login Page
- 📝 Form with a single input for Iranian mobile numbers
- ✅ Client-side validation required (valid formats:
  - 09xxxxxxxxx
  - +989xxxxxxxxx
  - 00989xxxxxxxxx)
- ▶️ On "Login" button click:
  - 🔗 Send GET request → https://randomuser.me/api/?results=1&nat=us
  - 📥 Retrieve user data (name, email, picture) → store in localStorage
  - 🔀 Redirect → Dashboard page

### 🖥 Dashboard Page
- 👋 Show welcome message with user's name
- 🚪 Logout button → clears localStorage + redirects to Login page
- 🔒 If no user data in localStorage → redirect to Login page

## 🎨 UI Components (Tailwind)
- ✍️ Input: label, error state, focus style, validation
- 🔘 Button: primary, disabled, loading states

## ⚙️ Technical Requirements
- ⚛️ Next.js App Router + TypeScript
- 🎨 Styling → Tailwind CSS only
- 📂 Clean, modular folder structure (UI components, lib for utils)
- 📱 Responsive design (mobile-first)
- 📐 Next.js best practices (layout, metadata, client components)
- 💾 User state/session → handled client-side with localStorage

## 🌟 Quality Expectations
- 🧹 Clean & readable code
- 🔤 Clear & consistent naming conventions
- ♿️ Accessibility (ARIA attributes, focus-visible states)
- 💬 Concise comments where needed
- 📘 README with setup + run instructions

## 🔄 Flow
1. 👤 User opens Login page → enters valid Iranian phone → clicks Login
2. 🌐 API called → data saved in localStorage → redirect to Dashboard
3. 🙌 Dashboard shows Welcome + user's name
4. 🚪 Logout → clear storage → redirect back to Login

## 🔍 Evaluation Criteria
- ✨ Code Quality → clean, modular, maintainable
- 🧑‍💻 TypeScript Usage → strong types, no any
- 🎨 UI/UX → responsive, clean Tailwind design
- 🔧 Logic → validation, API handling, redirect, auth state
- 📈 Scalability → reusable components & structure

## ⏰ Deadline
⚡️ Complete within 48 hours

## 📦 Deliverables
- 🔗 GitHub repo link (codebase)

لطفا بعد از اتمام تسک به ایدی تلگرامی لینک گیت هاب پروژه را برای دریافت بازخورد ارسال بفرمایید
با تشکر