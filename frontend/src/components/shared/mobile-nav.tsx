"use client";
import { motion } from "framer-motion";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { navSections } from "@/config/navigation";
import { cn } from "@/lib/utils";

export function MobileNav() {
  const pathname = usePathname();
  const allItems = navSections.flatMap((s) => s.items);
  // Show first 5 items
  const items = allItems.slice(0, 5);
  return (
    <nav className="lg:hidden fixed bottom-0 inset-x-0 z-30 border-t border-border/60 bg-background/90 backdrop-blur-xl">
      <ul className="grid grid-cols-5">
        {items.map((it) => {
          const active = pathname === it.href;
          return (
            <li key={it.href}>
              <Link
                href={it.href}
                className={cn(
                  "relative flex flex-col items-center justify-center gap-1 py-2.5",
                  active ? "text-electric" : "text-muted-foreground",
                )}
              >
                {active && (
                  <motion.div
                    layoutId="mobile-active"
                    className="absolute top-0 inset-x-4 h-0.5 bg-brand-gradient rounded-full"
                  />
                )}
                <it.icon className="size-4" />
                <span className="text-[10px]">{it.title.split(" ")[0]}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
