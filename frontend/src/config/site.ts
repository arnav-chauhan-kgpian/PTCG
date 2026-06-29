export const siteConfig = {
  name: "Pokémon AI",
  tagline: "Train. Analyze. Battle. Learn.",
  description:
    "Production-grade AlphaZero-style Pokémon TCG AI — train, analyze, battle, and explore your decks with neural search.",
  url: process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000",
  links: {
    github: "https://github.com/your-org/pokemon-ai",
    docs: "/about",
    twitter: "https://twitter.com/",
  },
  brandColors: {
    electric: "#4A8FFF",
    indigo: "#5E5CFF",
    purple: "#A855F7",
    gold: "#FFB627",
    yellow: "#FFCB05",
  },
} as const;

export type SiteConfig = typeof siteConfig;
