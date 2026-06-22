"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { ThemeToggle } from "@/components/ThemeToggle";
import { api, clearToken } from "@/lib/api";

export function TopBar() {
  const router = useRouter();
  const pathname = usePathname();
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
    retry: false,
  });
  if (pathname === "/login") return null;

  const model = health.data?.default_model;
  const shortModel = model ? model.split("/").slice(-1)[0] : null;
  const online = health.isSuccess && health.data?.ready;

  const navCls = (active: boolean) =>
    `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
      active ? "bg-surface2 text-fg" : "text-muted hover:text-fg"
    }`;

  return (
    <header className="sticky top-0 z-30 border-b bg-bg/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
        <div className="flex items-center gap-7">
          <Link href="/" className="group flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-primary to-accent2 text-sm font-black text-white shadow-glow">
              R
            </span>
            <span className="text-[15px] font-semibold tracking-tight">
              Rubric<span className="text-primary">Eval</span>
            </span>
          </Link>
          <nav className="hidden items-center gap-1 sm:flex">
            <Link href="/" className={navCls(pathname === "/")}>
              Tasks
            </Link>
            <Link href="/settings" className={navCls(pathname === "/settings")}>
              Settings
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-2.5">
          {shortModel && (
            <Link
              href="/settings"
              title={model}
              className="hidden chip border bg-surface2 text-muted hover:text-fg sm:inline-flex"
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${online ? "bg-good" : "bg-bad"}`}
              />
              {shortModel}
            </Link>
          )}
          <ThemeToggle />
          <button
            onClick={() => {
              clearToken();
              router.push("/login");
            }}
            className="rounded-lg px-3 py-1.5 text-sm text-muted transition hover:text-fg"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  );
}
