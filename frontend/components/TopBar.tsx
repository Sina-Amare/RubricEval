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
    `focus-ring px-2.5 py-1.5 text-sm font-medium transition sm:px-3 ${
      active ? "bg-surface2 text-fg" : "text-muted hover:text-fg"
    }`;

  return (
    <header className="glass-bar sticky top-0 z-30 border-b">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-4 py-3 sm:px-5">
        <div className="flex items-center gap-2 sm:gap-6">
          <Link href="/" className="focus-ring flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-primary to-accent2 text-sm font-black text-primary-fg shadow-glow">
              R
            </span>
            <span className="hidden text-[15px] font-semibold tracking-tight xs:inline">
              Rubric<span className="text-primary">Eval</span>
            </span>
          </Link>
          <nav className="flex items-center gap-0.5 sm:gap-1">
            <Link href="/" className={navCls(pathname === "/")}>
              Tasks
            </Link>
            <Link href="/settings" className={navCls(pathname === "/settings")}>
              Settings
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2.5">
          {shortModel && (
            <Link
              href="/settings"
              title={model}
              className="hidden chip border bg-surface2 text-muted hover:text-fg md:inline-flex"
            >
              <span className={`h-1.5 w-1.5 rounded-full ${online ? "bg-good" : "bg-bad"}`} />
              {shortModel}
            </Link>
          )}
          <ThemeToggle />
          <button
            onClick={() => {
              clearToken();
              router.push("/login");
            }}
            aria-label="Sign out"
            className="focus-ring grid h-9 w-9 place-items-center text-muted transition hover:text-fg sm:h-auto sm:w-auto sm:px-3 sm:py-1.5"
          >
            <span className="hidden text-sm sm:inline">Sign out</span>
            <svg className="sm:hidden" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" /></svg>
          </button>
        </div>
      </div>
    </header>
  );
}
