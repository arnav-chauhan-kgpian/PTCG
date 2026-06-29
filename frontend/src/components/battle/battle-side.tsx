"use client";
import { Library, Recycle, Sparkles } from "lucide-react";
import { PokemonToken } from "@/components/battle/pokemon-token";
import { PrizeCards } from "@/components/battle/prize-cards";
import { cn } from "@/lib/utils";
import type { BattleSide } from "@/services/battle";

export function BattleSidePanel({
  side, reversed = false, isTurn = false,
}: {
  side: BattleSide;
  reversed?: boolean;
  isTurn?: boolean;
}) {
  return (
    <div className={cn("relative rounded-2xl border border-border/40 bg-card/30 backdrop-blur-xl p-4 md:p-6", isTurn && "ring-2 ring-electric/40")}>
      {/* Header */}
      <div className={cn("flex items-center justify-between mb-4", reversed && "flex-row-reverse")}>
        <div className={cn("flex items-center gap-3", reversed && "flex-row-reverse")}>
          <div className={cn(
            "size-9 rounded-full grid place-items-center text-white text-xs font-bold shadow-lg",
            side.player === "you"
              ? "bg-brand-gradient shadow-electric/40 [background-size:200%_100%] animate-gradient-flow"
              : "bg-gradient-to-br from-rose-500 to-rose-700 shadow-rose-500/30"
          )}>
            {side.player === "you" ? "AI" : "OP"}
          </div>
          <div>
            <p className="font-semibold text-sm">{side.username}</p>
            <p className="text-[10px] text-muted-foreground">
              {side.player === "you" ? "Pokémon AI · Charizard ex deck" : "Opponent · Gardevoir ex deck"}
            </p>
          </div>
          {isTurn && (
            <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-electric/15 text-electric px-2 py-0.5 text-[10px] font-semibold">
              <Sparkles className="size-3" />
              Your turn
            </span>
          )}
        </div>
        <ZoneStats side={side} reversed={reversed} />
      </div>

      {/* Battle field */}
      <div className={cn("grid gap-4 items-center", reversed ? "grid-cols-[auto_1fr_auto] md:grid-cols-[auto_1fr_auto]" : "grid-cols-[auto_1fr_auto]")}>
        {/* Prize stack */}
        <div className="flex flex-col items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Prizes</span>
          <PrizeCards count={side.prize_count} ownership={side.player} />
          <span className="font-mono text-sm font-bold">{side.prize_count}/6</span>
        </div>

        {/* Active + bench */}
        <div className={cn("flex flex-col items-center gap-3", reversed && "flex-col-reverse")}>
          <div className="flex justify-center">
            <PokemonToken card={side.active} active variant="active" ownership={side.player} />
          </div>
          <div className="flex justify-center gap-2 flex-wrap">
            {Array.from({ length: 5 }).map((_, i) => (
              <PokemonToken key={i} card={side.bench[i] ?? null} variant="bench" ownership={side.player} />
            ))}
          </div>
        </div>

        {/* Discard */}
        <div className="flex flex-col items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Discard</span>
          <div className="rounded-lg border border-border/40 bg-card/40 h-12 w-9 grid place-items-center">
            <span className="font-mono text-sm font-bold">{side.discard_count}</span>
          </div>
          <span className="text-[10px] text-muted-foreground">Cards</span>
        </div>
      </div>

      {/* Hand row (you only) */}
      {side.player === "you" && <HandRow count={side.hand_count} deck={side.deck_count} />}
    </div>
  );
}

function ZoneStats({ side, reversed }: { side: BattleSide; reversed: boolean }) {
  return (
    <div className={cn("flex items-center gap-3", reversed && "flex-row-reverse")}>
      <Stat icon={Library} label="Deck" value={side.deck_count} />
      <Stat icon={Recycle} label="Hand" value={side.hand_count} />
    </div>
  );
}

function Stat({ icon: Icon, label, value }: { icon: any; label: string; value: number }) {
  return (
    <div className="flex flex-col items-center">
      <div className="flex items-center gap-1 text-muted-foreground">
        <Icon className="size-3" />
        <span className="text-[10px] uppercase tracking-wider">{label}</span>
      </div>
      <span className="font-mono font-bold text-sm tabular-nums">{value}</span>
    </div>
  );
}

function HandRow({ count, deck }: { count: number; deck: number }) {
  return (
    <div className="mt-4 pt-4 border-t border-border/40">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Hand · {count} cards</span>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Deck · {deck}</span>
      </div>
      <div className="flex gap-1 overflow-x-auto pb-1 scrollbar-none">
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className="shrink-0 h-16 w-12 rounded-lg border border-border/40 bg-gradient-to-br from-electric/15 via-purple/10 to-gold/5 backdrop-blur shadow-md"
            style={{ transform: `rotate(${(i - count / 2) * 1.5}deg)`, transformOrigin: "center bottom" }}
          />
        ))}
      </div>
    </div>
  );
}
