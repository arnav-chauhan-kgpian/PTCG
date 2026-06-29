"use client";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export function PrizeCards({ count, ownership }: { count: number; ownership: "you" | "opponent" }) {
  const taken = 6 - count;
  return (
    <div className={cn("grid grid-cols-2 gap-1.5", ownership === "opponent" && "rotate-180")}>
      {Array.from({ length: 6 }).map((_, i) => {
        const isTaken = i < taken;
        return (
          <motion.div
            key={i}
            initial={false}
            animate={isTaken ? { opacity: 0.2, scale: 0.9 } : { opacity: 1, scale: 1 }}
            className={cn(
              "h-9 w-6 rounded border backdrop-blur",
              isTaken
                ? "border-border/30 bg-transparent"
                : ownership === "you"
                ? "border-electric/30 bg-gradient-to-br from-electric/15 to-purple/15 shadow shadow-electric/20"
                : "border-rose-500/30 bg-gradient-to-br from-rose-500/15 to-rose-700/15 shadow shadow-rose-500/20",
            )}
            title={isTaken ? "Taken" : `Prize ${i + 1}`}
          />
        );
      })}
    </div>
  );
}
