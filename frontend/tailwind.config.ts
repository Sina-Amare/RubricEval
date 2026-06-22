import type { Config } from "tailwindcss";

/** Resolve a CSS variable as an rgb() color that supports Tailwind opacity.
 *  Tailwind accepts a function at runtime; we cast so the static Config type
 *  (which expects a string) is satisfied. */
function v(name: string): string {
  return ((opts: { opacityValue?: string }) =>
    opts.opacityValue === undefined
      ? `rgb(var(${name}))`
      : `rgb(var(${name}) / ${opts.opacityValue})`) as unknown as string;
}

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: v("--bg"),
        surface: v("--surface"),
        surface2: v("--surface-2"),
        fg: v("--text"),
        muted: v("--muted"),
        primary: v("--primary"),
        "primary-fg": v("--primary-fg"),
        accent2: v("--accent-2"),
        good: v("--good"),
        warn: v("--warn"),
        bad: v("--bad"),
        border: "var(--border-c)",
      },
      borderColor: { DEFAULT: "var(--border-c)" },
      fontFamily: {
        sans: [
          "var(--font-sans)",
          "ui-sans-serif",
          "system-ui",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: { xl: "0.9rem", "2xl": "1.1rem" },
      boxShadow: {
        soft: "var(--shadow-soft)",
        card: "var(--shadow-card)",
        glow: "0 10px 40px -12px rgb(var(--primary) / 0.45)",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-ring": {
          "0%": { boxShadow: "0 0 0 0 rgb(var(--primary) / 0.5)" },
          "100%": { boxShadow: "0 0 0 10px rgb(var(--primary) / 0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease both",
        "pulse-ring": "pulse-ring 1.4s ease-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
