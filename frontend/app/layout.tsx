import "./globals.css";

import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { TopBar } from "@/components/TopBar";

import { Providers } from "./providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "RubricEval — rubric-driven code evaluation",
  description:
    "Define a rubric, submit a repo or zip, watch a live evaluation, and get an "
    + "evidence-backed accept / review / reject decision.",
};

// Set the theme class before paint to avoid a flash of the wrong theme.
const themeScript = `(function(){try{var t=localStorage.getItem('theme');var d=t?t==='dark':!window.matchMedia('(prefers-color-scheme: light)').matches;document.documentElement.classList.toggle('dark',d);}catch(e){document.documentElement.classList.add('dark');}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <Providers>
          <TopBar />
          <main className="mx-auto max-w-6xl px-5 py-8 md:py-10">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
