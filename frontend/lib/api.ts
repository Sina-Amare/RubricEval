import type {
  Health,
  ProviderConfig,
  ProviderTestResult,
  RubricDraft,
  Review,
  ReviewSummary,
  Submission,
  Task,
} from "./types";

export interface ProviderConfigInput {
  name: string;
  provider: string;
  model_id: string;
  api_key: string;
  is_default: boolean;
}

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8090";

const TOKEN_KEY = "operator_token";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${getToken()}`);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_BASE}/api${path}`, { ...init, headers });
  if (res.status === 401 && typeof window !== "undefined") {
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
    throw new ApiError(401, "Unauthorized");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // health
  health: () => req<Health>("/health"),

  // provider configs (BYOK)
  listProviders: () => req<ProviderConfig[]>("/provider-configs"),
  createProvider: (body: ProviderConfigInput) =>
    req<ProviderConfig>("/provider-configs", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  setDefaultProvider: (id: string) =>
    req<ProviderConfig>(`/provider-configs/${id}/default`, { method: "POST" }),
  deleteProvider: (id: string) =>
    req<void>(`/provider-configs/${id}`, { method: "DELETE" }),
  testProvider: (body: { provider: string; model_id: string; api_key: string }) =>
    req<ProviderTestResult>("/provider-configs/test", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  testSavedProvider: (id: string) =>
    req<ProviderTestResult>(`/provider-configs/${id}/test`, { method: "POST" }),

  // tasks
  listTasks: () => req<Task[]>("/tasks"),
  getTask: (id: string) => req<Task>(`/tasks/${id}`),
  createTask: (name: string) =>
    req<Task>("/tasks", { method: "POST", body: JSON.stringify({ name }) }),
  deleteTask: (id: string) => req<void>(`/tasks/${id}`, { method: "DELETE" }),
  saveRubric: (id: string, draft: RubricDraft) =>
    req<RubricDraft>(`/tasks/${id}/rubric`, {
      method: "PUT",
      body: JSON.stringify(draft),
    }),
  publishRubric: (id: string) =>
    req<{ version_number: number; content_hash: string }>(
      `/tasks/${id}/rubric/publish`,
      { method: "POST" },
    ),

  // submissions
  submitGithub: (github_url: string) =>
    req<Submission>("/submissions/github", {
      method: "POST",
      body: JSON.stringify({ github_url }),
    }),
  submitZip: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return req<Submission>("/submissions/zip", { method: "POST", body: fd });
  },
  getSubmission: (id: string) => req<Submission>(`/submissions/${id}`),
  fileContent: (submissionId: string, path: string) =>
    req<{ path: string; language: string | null; content: string }>(
      `/submissions/${submissionId}/files/content?path=${encodeURIComponent(path)}`,
    ),

  // reviews
  createReview: (task_id: string, submission_id: string) =>
    req<Review>("/reviews", {
      method: "POST",
      body: JSON.stringify({ task_id, submission_id }),
    }),
  getReview: (id: string) => req<Review>(`/reviews/${id}`),
  listReviews: (taskId?: string) =>
    req<ReviewSummary[]>(`/reviews${taskId ? `?task_id=${taskId}` : ""}`),
};

export function streamUrl(reviewId: string): string {
  return `${API_BASE}/api/reviews/${reviewId}/stream?token=${encodeURIComponent(getToken())}`;
}
