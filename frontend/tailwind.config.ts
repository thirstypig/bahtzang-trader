import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        surface:  "rgb(var(--surface) / <alpha-value>)",
        card:     "rgb(var(--card) / <alpha-value>)",
        "card-alt": "rgb(var(--card-alt) / <alpha-value>)",
        border:   "rgb(var(--border) / <alpha-value>)",
        "border-strong": "rgb(var(--border-strong) / <alpha-value>)",
        primary:  "rgb(var(--text-primary) / <alpha-value>)",
        secondary: "rgb(var(--text-secondary) / <alpha-value>)",
        muted:    "rgb(var(--text-muted) / <alpha-value>)",
        accent:   "rgb(var(--accent) / <alpha-value>)",
        "accent-light": "rgb(var(--accent-light) / <alpha-value>)",
        "accent-text":  "rgb(var(--accent-text) / <alpha-value>)",
        danger:   "rgb(var(--danger) / <alpha-value>)",
      },
    },
  },
  plugins: [],
};
export default config;
