"use client";
import { motion } from "framer-motion";
import { ArrowRight, Github, Menu, Sparkles, X } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { siteConfig } from "@/config/site";

const links = [
  { href: "#features", label: "Features" },
  { href: "#architecture", label: "Architecture" },
  { href: "#performance", label: "Performance" },
  { href: "#demo", label: "Demo" },
];

export function LandingNav() {
  const [scrolled, setScrolled] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <motion.header
      initial={{ y: -40, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4 }}
      className={`fixed inset-x-0 top-0 z-40 transition-all ${
        scrolled ? "border-b border-border/40 bg-background/70 backdrop-blur-xl" : ""
      }`}
    >
      <div className="container flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2 group">
          <div className="relative">
            <div className="size-8 rounded-xl bg-brand-gradient shadow-lg shadow-electric/30 [background-size:200%_100%] animate-gradient-flow flex items-center justify-center">
              <Sparkles className="size-4 text-white" />
            </div>
            <div className="absolute inset-0 size-8 rounded-xl bg-brand-gradient blur-md opacity-50 group-hover:opacity-80 transition-opacity" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="font-display font-bold text-base tracking-tight">{siteConfig.name}</span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider">v1.0</span>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors rounded-md"
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <a href={siteConfig.links.github} target="_blank" rel="noreferrer">
              <Github className="size-4" />
              GitHub
            </a>
          </Button>
          <Button asChild variant="gradient" size="sm" className="shadow">
            <Link href="/dashboard">
              Launch App
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>

        <Button variant="ghost" size="icon" className="md:hidden" onClick={() => setOpen((s) => !s)}>
          {open ? <X /> : <Menu />}
        </Button>
      </div>

      {open && (
        <div className="md:hidden border-t border-border/40 bg-background/95 backdrop-blur-xl">
          <div className="container py-4 space-y-1">
            {links.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="block px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-accent rounded-md"
              >
                {l.label}
              </Link>
            ))}
            <Link
              href="/dashboard"
              className="block px-3 py-2 text-sm font-medium text-electric"
            >
              Launch App →
            </Link>
          </div>
        </div>
      )}
    </motion.header>
  );
}
