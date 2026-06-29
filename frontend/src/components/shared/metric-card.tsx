"use client";
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: string | number;
  unit?: string;
  trend?: number;            // -1..1
  trendLabel?: string;
  icon?: LucideIcon;
  accent?: "electric" | "indigo" | "purple" | "gold" | "emerald" | "rose";
  loading?: boolean;
  description?: string;
  delay?: number;
  className?: string;
}

const accentMap = {
  electric: { glow: "from-electric/40 to-electric/0", text: "text-electric", iconBg: "bg-electric/10 text-electric border-electric/20" },
  indigo: { glow: "from-indigo/40 to-indigo/0", text: "text-indigo-light", iconBg: "bg-indigo/10 text-indigo-light border-indigo/20" },
  purple: { glow: "from-purple/40 to-purple/0", text: "text-purple-light", iconBg: "bg-purple/10 text-purple-light border-purple/20" },
  gold: { glow: "from-gold/40 to-gold/0", text: "text-gold-light", iconBg: "bg-gold/10 text-gold-light border-gold/20" },
  emerald: { glow: "from-emerald-500/40 to-emerald-500/0", text: "text-emerald-400", iconBg: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
  rose: { glow: "from-rose-500/40 to-rose-500/0", text: "text-rose-400", iconBg: "bg-rose-500/10 text-rose-400 border-rose-500/20" },
};

export function MetricCard({
  label, value, unit, trend, trendLabel, icon: Icon, accent = "electric",
  loading, description, delay = 0, className,
}: MetricCardProps) {
  const a = accentMap[accent];
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        "relative overflow-hidden rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-5 shadow-xl",
        "hover:border-border/80 hover:bg-card/60 transition-colors duration-300 group",
        className,
      )}
    >
      <div className={cn("absolute -top-12 -right-12 size-48 rounded-full bg-gradient-radial opacity-50 blur-3xl pointer-events-none", a.glow)} />
      <div className="relative flex items-start justify-between gap-3">
        <div className="space-y-1.5 min-w-0">
          <p className="text-xs uppercase tracking-wider text-muted-foreground font-medium truncate">{label}</p>
          <div className="flex items-baseline gap-1.5">
            {loading ? (
              <span className="h-7 w-20 rounded bg-muted/60 animate-pulse" />
            ) : (
              <>
                <h3 className={cn("text-2xl md:text-3xl font-bold tracking-tight font-display", a.text)}>
                  {value}
                </h3>
                {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
              </>
            )}
          </div>
          {description && (
            <p className="text-xs text-muted-foreground leading-relaxed mt-1">{description}</p>
          )}
        </div>
        {Icon && (
          <div className={cn("flex items-center justify-center size-10 rounded-xl border", a.iconBg)}>
            <Icon className="size-5" />
          </div>
        )}
      </div>
      {trend != null && (
        <div className="relative mt-3 flex items-center gap-1.5">
          <div className={cn(
            "inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-xs font-medium",
            trend >= 0 ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400",
          )}>
            {trend >= 0 ? <ArrowUpRight className="size-3" /> : <ArrowDownRight className="size-3" />}
            {Math.abs(trend * 100).toFixed(1)}%
          </div>
          {trendLabel && <span className="text-xs text-muted-foreground">{trendLabel}</span>}
        </div>
      )}
    </motion.div>
  );
}
