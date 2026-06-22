import { defineConfig } from "@playwright/test";

// The backend must be running separately with LLM_BACKEND=fake and
// OPERATOR_TOKEN matching e2e/full-flow.spec.ts (see scripts/e2e.ps1 / Makefile).
export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  webServer: {
    command: "npm run start",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
