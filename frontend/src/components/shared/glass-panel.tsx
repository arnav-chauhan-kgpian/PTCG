"use client";
import { motion, type HTMLMotionProps } from "framer-motion";
import * as React from "react";
import { cn } from "@/lib/utils";

interface GlassPanelProps extends HTMLMotionProps<"div"> {
  glow?: "blue" | "purple" | "gold" | "none";
  variant?: "default" | "strong";
}

export const GlassPanel = React.forwardRef<HTMLDivElement, GlassPanelProps>(
  ({ className, glow = "none", variant = "default", children, ...props }, ref) => (
    <motion.div
      ref={ref}
      className={cn(
        "relative rounded-2xl border border-white/10 bg-white/[0.03] backdrop-blur-xl backdrop-saturate-150 shadow-2xl",
        variant === "strong" && "bg-white/[0.06] border-white/20",
        glow === "blue" && "glow-blue",
        glow === "purple" && "glow-purple",
        glow === "gold" && "glow-gold",
        className,
      )}
      {...props}
    >
      <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-white/5 via-transparent to-transparent pointer-events-none" />
      {children}
    </motion.div>
  ),
);
GlassPanel.displayName = "GlassPanel";
