"use client";
import { Bell, Github, Moon, Search, Sun, User } from "lucide-react";
import { useTheme } from "next-themes";
import Link from "next/link";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { siteConfig } from "@/config/site";
import { useCommandPalette } from "@/store/command-palette";

export function Topbar() {
  const { theme, setTheme } = useTheme();
  const { toggle } = useCommandPalette();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border/40 bg-background/60 backdrop-blur-xl px-4 md:px-6">
      <Button
        variant="glass"
        className="flex-1 max-w-md justify-between text-muted-foreground"
        onClick={toggle}
      >
        <span className="flex items-center gap-2">
          <Search className="size-4" />
          <span className="hidden sm:inline">Search anything…</span>
          <span className="sm:hidden">Search</span>
        </span>
        <kbd className="hidden sm:inline-flex items-center gap-1 rounded border border-border/60 bg-background/60 px-1.5 py-0.5 text-[10px] font-mono">
          ⌘K
        </kbd>
      </Button>

      <div className="ml-auto flex items-center gap-1">
        <Button variant="ghost" size="icon" asChild>
          <a href={siteConfig.links.github} target="_blank" rel="noreferrer" aria-label="GitHub">
            <Github className="size-4" />
          </a>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label="Toggle theme"
        >
          {mounted && theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </Button>
        <Button variant="ghost" size="icon" aria-label="Notifications" className="relative">
          <Bell className="size-4" />
          <span className="absolute top-2 right-2 size-1.5 rounded-full bg-electric" />
        </Button>
        <Link
          href="/settings"
          className="ml-1 inline-flex items-center justify-center size-9 rounded-full bg-brand-gradient shadow shadow-electric/30 hover:shadow-purple/40 transition-shadow"
        >
          <User className="size-4 text-white" />
        </Link>
      </div>
    </header>
  );
}
