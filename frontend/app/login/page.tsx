"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Spinner } from "@/components/ui";
import { setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [token, setTok] = useState("");
  const [busy, setBusy] = useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setToken(token.trim());
    router.push("/");
  }

  return (
    <div className="grid min-h-[70vh] place-items-center">
      <div className="w-full max-w-sm animate-fade-up">
        <div className="mb-6 flex items-center justify-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-lg bg-gradient-to-br from-primary to-accent2 text-base font-black text-primary-fg shadow-glow">
            R
          </span>
          <span className="text-lg font-semibold tracking-tight">
            Rubric<span className="text-primary">Eval</span>
          </span>
        </div>
        <div className="card p-7">
          <h1 className="text-xl font-semibold">Welcome back</h1>
          <p className="mb-6 mt-1 text-sm text-muted">
            Enter your operator token to access the evaluation panel.
          </p>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label">Operator token</label>
              <input
                className="input"
                type="password"
                placeholder="OPERATOR_TOKEN"
                value={token}
                onChange={(e) => setTok(e.target.value)}
                data-testid="token-input"
                autoFocus
              />
            </div>
            <button className="btn-primary w-full" type="submit" data-testid="login-btn">
              {busy ? <Spinner /> : "Sign in"}
            </button>
          </form>
        </div>
        <p className="mt-4 text-center text-xs text-muted">
          Single-operator access · token is stored locally in your browser.
        </p>
      </div>
    </div>
  );
}
