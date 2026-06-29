"use client";
import { motion } from "framer-motion";
import * as React from "react";
import { EnergyIcon } from "@/components/shared/energy-icon";
import { cn } from "@/lib/utils";
import type { BattleCard } from "@/services/battle";

const typeColors: Record<string, string> = {
  Fire: "from-orange-500/30 to-red-500/10",
  Water: "from-blue-500/30 to-blue-700/10",
  Grass: "from-emerald-500/30 to-emerald-700/10",
  Lightning: "from-yellow-400/30 to-yellow-600/10",
  Psychic: "from-purple-500/30 to-purple-700/10",
  Fighting: "from-red-700/30 to-red-900/10",
  Colorless: "from-zinc-400/30 to-zinc-600/10",
  Metal: "from-zinc-300/30 to-zinc-500/10",
  Dark: "from-zinc-700/30 to-zinc-900/30",
};

interface Props {
  card: BattleCard | null;
  active?: boolean;
  variant?: "active" | "bench";
  ownership: "you" | "opponent";
  onClick?: () => void;
}

export function PokemonToken({ card, active, variant = "active", ownership, onClick }: Props) {
  if (!card) return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-xl border border-dashed border-border/40 bg-card/20 grid place-items-center text-xs text-muted-foreground/60",
        variant === "active" ? "size-32 md:size-40" : "size-16 md:size-20",
      )}
    >
      empty
    </button>
  );

  const hpPercent = (card.hp_current / card.hp_max) * 100;
  const hpColor =
    hpPercent > 60 ? "from-emerald-500 to-emerald-400"
    : hpPercent > 30 ? "from-amber-500 to-amber-400"
    : "from-rose-500 to-rose-400";

  return (
    <motion.button
      onClick={onClick}
      whileHover={{ scale: 1.04, y: -2 }}
      whileTap={{ scale: 0.97 }}
      initial={{ scale: 0.85, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ type: "spring", stiffness: 320, damping: 24 }}
      className={cn(
        "relative group rounded-2xl border bg-card/60 backdrop-blur-xl shadow-xl overflow-hidden text-left transition-all",
        active ? "border-electric/50 shadow-electric/20" : "border-border/40",
        variant === "active"
          ? "size-32 md:size-44 p-3"
          : "size-16 md:size-20 p-1.5",
      )}
    >
      <div
        className={cn(
          "absolute inset-0 bg-gradient-to-br opacity-50 pointer-events-none",
          typeColors[card.type] ?? "from-zinc-400/20 to-zinc-600/10",
        )}
      />
      <div className={cn(
        "absolute inset-0 pointer-events-none",
        active && "ring-2 ring-electric/40 ring-offset-2 ring-offset-card animate-pulse"
      )} />

      {/* HP bar */}
      <div className="absolute top-0 inset-x-0 h-1.5 bg-black/30">
        <motion.div
          initial={{ width: "100%" }}
          animate={{ width: `${hpPercent}%` }}
          transition={{ duration: 0.5 }}
          className={cn("h-full bg-gradient-to-r", hpColor)}
        />
      </div>

      <div className="relative h-full flex flex-col justify-between">
        <div>
          <p className={cn(
            "font-semibold truncate",
            variant === "active" ? "text-sm md:text-base" : "text-[10px]",
          )}>
            {card.name}
          </p>
          {variant === "active" && (
            <p className="text-[10px] text-muted-foreground mt-0.5">{card.stage}</p>
          )}
        </div>

        {variant === "active" && (
          <div className="space-y-1.5 mt-2">
            <div className="flex items-center justify-between text-xs">
              <span className="font-mono tabular-nums font-bold">
                {card.hp_current}/{card.hp_max}
              </span>
              <span className="text-muted-foreground">HP</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {card.attached_energy.map((e, i) => (
                <EnergyIcon key={i} type={e} size="sm" />
              ))}
            </div>
            {card.conditions.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {card.conditions.map((c) => (
                  <span key={c} className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-400 font-semibold">
                    {c}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
        {variant === "bench" && (
          <div className="flex items-center gap-0.5">
            {card.attached_energy.slice(0, 3).map((e, i) => (
              <EnergyIcon key={i} type={e} size="sm" />
            ))}
          </div>
        )}
      </div>

      {/* ownership indicator */}
      <div className={cn(
        "absolute -top-1 -right-1 size-3 rounded-full",
        ownership === "you" ? "bg-electric" : "bg-rose-500",
      )} />
    </motion.button>
  );
}
