"use client";
import { Activity, ArrowLeftRight, Crosshair, FlaskRound, Sparkles, Wand2 } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { BattleLog as Log } from "@/services/battle";

const kindIcons: Record<string, { icon: any; color: string }> = {
  attack: { icon: Crosshair, color: "text-rose-400 bg-rose-500/10" },
  trainer: { icon: FlaskRound, color: "text-purple-light bg-purple/10" },
  ability: { icon: Wand2, color: "text-electric bg-electric/10" },
  energy: { icon: Sparkles, color: "text-gold-light bg-gold/10" },
  evolve: { icon: ArrowLeftRight, color: "text-indigo-light bg-indigo/10" },
  system: { icon: Activity, color: "text-muted-foreground bg-muted/30" },
};

export function BattleLog({ log }: { log: Log[] }) {
  return (
    <div className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl overflow-hidden flex flex-col h-full">
      <div className="p-4 border-b border-border/40 flex items-center justify-between">
        <div>
          <p className="font-semibold text-sm">Battle log</p>
          <p className="text-[10px] text-muted-foreground">Live action history</p>
        </div>
        <span className="text-[10px] font-mono text-muted-foreground bg-muted/30 rounded px-2 py-0.5">
          {log.length} events
        </span>
      </div>
      <ScrollArea className="flex-1">
        <ul className="p-3 space-y-1.5">
          {[...log].reverse().map((entry) => {
            const cfg = kindIcons[entry.kind] ?? kindIcons.system;
            const isYou = entry.player === "you";
            return (
              <li
                key={entry.id}
                className={cn(
                  "flex items-start gap-2 rounded-lg p-2.5 text-xs border border-border/30 backdrop-blur",
                  isYou ? "bg-electric/5" : "bg-rose-500/5",
                )}
              >
                <div className={cn("size-6 rounded-md grid place-items-center shrink-0", cfg.color)}>
                  <cfg.icon className="size-3" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className={cn("font-semibold text-[10px] uppercase tracking-wider", isYou ? "text-electric" : "text-rose-400")}>
                      {isYou ? "You" : "Opp"}
                    </span>
                    <span className="text-[9px] text-muted-foreground">T{entry.turn}</span>
                    <span className="text-[9px] text-muted-foreground ml-auto">{formatRelativeTime(entry.timestamp)}</span>
                  </div>
                  <p className="mt-0.5 text-foreground/90 leading-snug">{entry.text}</p>
                </div>
              </li>
            );
          })}
        </ul>
      </ScrollArea>
    </div>
  );
}
