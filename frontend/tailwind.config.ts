import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    container: { center: true, padding: "2rem", screens: { "2xl": "1400px" } },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Brand palette
        electric: { DEFAULT: "#4A8FFF", light: "#6EA5FF", dark: "#1A5FE0" },
        indigo: { DEFAULT: "#5E5CFF", light: "#8584FF", dark: "#3936D6" },
        purple: { DEFAULT: "#A855F7", light: "#C084FC", dark: "#7E22CE" },
        gold: { DEFAULT: "#FFB627", light: "#FFCD5E", dark: "#D69400" },
        pokeyellow: { DEFAULT: "#FFCB05", light: "#FFE066" },
        // Pokémon energy types
        type: {
          grass: "#7BC74D",
          fire: "#FF7038",
          water: "#54A4E5",
          lightning: "#FFC845",
          psychic: "#B870C8",
          fighting: "#C04848",
          dark: "#4F5468",
          metal: "#A8B0B8",
          dragon: "#7B62A3",
          colorless: "#E0DDD8",
          fairy: "#E879A9",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
        display: ["var(--font-display)", "var(--font-geist-sans)", "sans-serif"],
      },
      backgroundImage: {
        "gradient-radial": "radial-gradient(ellipse at center, var(--tw-gradient-stops))",
        "brand-gradient":
          "linear-gradient(135deg, #4A8FFF 0%, #5E5CFF 35%, #A855F7 70%, #FFB627 100%)",
        "brand-gradient-subtle":
          "linear-gradient(135deg, rgba(74, 143, 255, 0.08) 0%, rgba(168, 85, 247, 0.08) 100%)",
        "grid-pattern":
          "linear-gradient(to right, rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.04) 1px, transparent 1px)",
      },
      backgroundSize: { "grid-pattern": "32px 32px" },
      animation: {
        "fade-in": "fadeIn 400ms ease-out",
        "fade-in-up": "fadeInUp 600ms cubic-bezier(0.16, 1, 0.3, 1)",
        "slide-in-right": "slideInRight 300ms cubic-bezier(0.16, 1, 0.3, 1)",
        shimmer: "shimmer 2.5s linear infinite",
        glow: "glow 2.5s ease-in-out infinite",
        float: "float 6s ease-in-out infinite",
        "spin-slow": "spin 20s linear infinite",
        "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "gradient-flow": "gradientFlow 8s ease infinite",
        "card-tilt": "cardTilt 4s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        fadeInUp: {
          "0%": { opacity: "0", transform: "translateY(16px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideInRight: {
          "0%": { opacity: "0", transform: "translateX(20px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        glow: {
          "0%, 100%": { boxShadow: "0 0 20px rgba(94, 92, 255, 0.3)" },
          "50%": { boxShadow: "0 0 40px rgba(94, 92, 255, 0.6)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-12px)" },
        },
        gradientFlow: {
          "0%, 100%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
        },
        cardTilt: {
          "0%, 100%": { transform: "rotateY(-2deg) rotateX(2deg)" },
          "50%": { transform: "rotateY(2deg) rotateX(-2deg)" },
        },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
export default config;
