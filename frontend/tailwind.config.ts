import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        surface: "hsl(var(--surface))",
        card: "hsl(var(--card))",
        border: "hsl(var(--border))",
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        cta: { DEFAULT: "hsl(var(--cta))", foreground: "hsl(var(--cta-foreground))" },
        nav: { DEFAULT: "hsl(var(--nav))", foreground: "hsl(var(--nav-foreground))" },
        bull: "hsl(var(--bull))",
        bear: "hsl(var(--bear))",
        warn: "hsl(var(--warn))",
        ring: "hsl(var(--ring))",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      borderRadius: { lg: "1rem", md: "0.75rem", sm: "0.5rem" },
      boxShadow: {
        card: "0 10px 30px -12px rgba(33, 72, 140, 0.18), 0 2px 6px -2px rgba(33, 72, 140, 0.06)",
        soft: "0 4px 14px -6px rgba(33, 72, 140, 0.18)",
      },
    },
  },
  plugins: [],
};

export default config;
