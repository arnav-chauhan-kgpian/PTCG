"use client";
import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { navSections } from "@/config/navigation";
import { siteConfig } from "@/config/site";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden lg:flex w-64 shrink-0 flex-col border-r border-border/40 bg-card/30 backdrop-blur-xl">
      <Link href="/" className="flex items-center gap-2 px-6 h-16 border-b border-border/40 group">
        <div className="relative">
          <div className="size-8 rounded-xl bg-brand-gradient shadow-lg shadow-electric/30 [background-size:200%_100%] animate-gradient-flow flex items-center justify-center">
            <Sparkles className="size-4 text-white" />
          </div>
          <div className="absolute inset-0 size-8 rounded-xl bg-brand-gradient blur-md opacity-50 group-hover:opacity-80 transition-opacity" />
        </div>
        <div className="leading-none">
          <p className="font-display font-bold text-sm">{siteConfig.name}</p>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">v1.0</p>
        </div>
      </Link>

      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-5 scrollbar-none">
        {navSections.map((section) => (
          <div key={section.label}>
            <p className="px-3 mb-2 text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
              {section.label}
            </p>
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className={cn(
                        "relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors group",
                        active
                          ? "bg-card/80 text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground hover:bg-card/40",
                      )}
                    >
                      {active && (
                        <motion.div
                          layoutId="sidebar-active"
                          className="absolute inset-0 rounded-lg border border-border/60 bg-gradient-to-r from-electric/10 to-purple/10"
                          transition={{ type: "spring", stiffness: 380, damping: 30 }}
                        />
                      )}
                      <item.icon className={cn("size-4 relative shrink-0", active && "text-electric")} />
                      <span className="relative flex-1 truncate">{item.title}</span>
                      {item.badge && (
                        <Badge variant="info" className="relative h-4 px-1.5 text-[9px]">{item.badge}</Badge>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-border/40 p-4">
        <div className="rounded-xl border border-border/40 bg-card/40 p-3 backdrop-blur">
          <div className="flex items-center gap-2 mb-1.5">
            <div className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <p className="text-xs font-medium">All systems normal</p>
          </div>
          <p className="text-[10px] text-muted-foreground leading-relaxed">
            1,065 tests passing · 90% coverage · simulator 1.0
          </p>
        </div>
      </div>
    </aside>
  );
}
