"use client";
import { Command } from "cmdk";
import { Activity, BarChart3, Brain, Gamepad2, Hammer, LayoutDashboard, Library, Microscope, Search, Settings, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { useKeyboardShortcut } from "@/hooks/use-keyboard-shortcut";
import { useCommandPalette } from "@/store/command-palette";

const items = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/dashboard", group: "Navigate" },
  { icon: Gamepad2, label: "Battle Arena", href: "/battle", group: "Navigate" },
  { icon: Hammer, label: "Deck Builder", href: "/deck-builder", group: "Navigate" },
  { icon: Brain, label: "Deck Analyzer", href: "/deck-analyzer", group: "Navigate" },
  { icon: Library, label: "Card Database", href: "/cards", group: "Navigate" },
  { icon: Microscope, label: "Game Analysis", href: "/analysis", group: "Navigate" },
  { icon: Activity, label: "Training", href: "/training", group: "Navigate" },
  { icon: BarChart3, label: "Benchmarks", href: "/benchmarks", group: "Navigate" },
  { icon: Settings, label: "Settings", href: "/settings", group: "Navigate" },
  { icon: Sparkles, label: "About", href: "/about", group: "Navigate" },
];

export function CommandPalette() {
  const { open, setOpen, toggle } = useCommandPalette();
  const router = useRouter();
  useKeyboardShortcut({ key: "k", meta: true, ctrl: true, preventDefault: true, onTrigger: toggle });
  useKeyboardShortcut({ key: "Escape", onTrigger: () => setOpen(false) });

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-[55] flex items-start justify-center p-4 pt-[20vh] bg-background/80 backdrop-blur-md animate-fade-in"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-xl rounded-2xl border border-border/60 bg-card/90 backdrop-blur-2xl shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <Command label="Command Menu" shouldFilter className="w-full">
              <div className="flex items-center gap-2 border-b border-border/40 px-4 py-3">
                <Search className="size-4 text-muted-foreground" />
                <Command.Input
                  placeholder="Search pages, decks, cards…"
                  className="flex-1 bg-transparent text-sm placeholder:text-muted-foreground outline-none"
                />
                <kbd className="rounded border border-border/60 bg-background/60 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">ESC</kbd>
              </div>
              <Command.List className="max-h-[60vh] overflow-y-auto p-2">
                <Command.Empty className="px-3 py-6 text-center text-sm text-muted-foreground">
                  No results found.
                </Command.Empty>
                <Command.Group heading="Navigate" className="px-2 pb-2 [&_[cmdk-group-heading]]:text-[10px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wider [&_[cmdk-group-heading]]:text-muted-foreground [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-2">
                  {items.map(({ icon: Icon, label, href }) => (
                    <Command.Item
                      key={href}
                      value={label}
                      onSelect={() => {
                        router.push(href);
                        setOpen(false);
                      }}
                      className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm aria-selected:bg-accent aria-selected:text-accent-foreground cursor-pointer"
                    >
                      <Icon className="size-4 text-muted-foreground" />
                      <span className="flex-1">{label}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              </Command.List>
            </Command>
          </div>
        </div>
      )}
    </>
  );
}
