import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg, #08090B)",
        surface: {
          DEFAULT: "var(--surface, #111214)",
          raised: "var(--surface-raised, #17181C)",
          muted: "var(--surface-muted, #202126)",
        },
        border: "var(--border, #2B2C32)",
        text: {
          primary: "var(--text-primary, #F4F4F6)",
          secondary: "var(--text-secondary, #B7B8C2)",
          muted: "var(--text-muted, #858692)",
        },
        accent: {
          DEFAULT: "var(--accent, #9B72F2)",
          strong: "var(--accent-strong, #7C4DFF)",
        },
        success: "var(--success, #9BE34A)",
        warning: "var(--warning, #F6B94A)",
        danger: "var(--danger, #FF624F)",
        chart: {
          grid: "var(--chart-grid, #292A30)",
        },
      },
      borderRadius: {
        card: "18px",
        control: "10px",
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
      },
      spacing: {
        "18": "4.5rem",
      },
    },
  },
  plugins: [],
};

export default config;
