import { Github, Twitter } from "lucide-react";
import Link from "next/link";
import { siteConfig } from "@/config/site";

const groups = [
  {
    title: "Product",
    links: [
      { label: "Dashboard", href: "/dashboard" },
      { label: "Battle Arena", href: "/battle" },
      { label: "Deck Builder", href: "/deck-builder" },
      { label: "Card Database", href: "/cards" },
    ],
  },
  {
    title: "Engine",
    links: [
      { label: "Training", href: "/training" },
      { label: "Benchmarks", href: "/benchmarks" },
      { label: "Game Analysis", href: "/analysis" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Documentation", href: "/about" },
      { label: "GitHub", href: siteConfig.links.github },
      { label: "Twitter", href: siteConfig.links.twitter },
    ],
  },
];

export function LandingFooter() {
  return (
    <footer className="relative border-t border-border/40 mt-16">
      <div className="container py-12 md:py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-12">
          <div className="col-span-2">
            <div className="flex items-center gap-2 mb-3">
              <div className="size-7 rounded-lg bg-brand-gradient shadow shadow-electric/30 [background-size:200%_100%] animate-gradient-flow" />
              <span className="font-display font-bold text-base">{siteConfig.name}</span>
            </div>
            <p className="text-sm text-muted-foreground max-w-sm">
              An AlphaZero-class Pokémon TCG AI framework — production-grade,
              fully open-source, ready for the Kaggle Battle Challenge.
            </p>
            <div className="mt-4 flex items-center gap-2">
              <Link href={siteConfig.links.github} className="size-9 rounded-lg border border-border/60 inline-flex items-center justify-center hover:bg-accent transition" aria-label="GitHub">
                <Github className="size-4" />
              </Link>
              <Link href={siteConfig.links.twitter} className="size-9 rounded-lg border border-border/60 inline-flex items-center justify-center hover:bg-accent transition" aria-label="Twitter">
                <Twitter className="size-4" />
              </Link>
            </div>
          </div>
          {groups.map((g) => (
            <div key={g.title}>
              <h3 className="font-display font-semibold text-sm mb-3">{g.title}</h3>
              <ul className="space-y-2">
                {g.links.map((l) => (
                  <li key={l.href}>
                    <Link href={l.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-12 pt-6 border-t border-border/40 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            © {new Date().getFullYear()} {siteConfig.name}. MIT-licensed open-source project.
          </p>
          <p className="text-xs text-muted-foreground">
            Built with Next.js, Tailwind, Framer Motion, shadcn/ui.
          </p>
        </div>
      </div>
    </footer>
  );
}
