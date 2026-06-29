"use client";
import { motion } from "framer-motion";
import { ArrowRight, Brain, Target, Trophy, Zap } from "lucide-react";
import * as React from "react";
import { StatBadge } from "@/components/shared/stat-badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn, formatPercent } from "@/lib/utils";
import type { BattleAction, BattleState } from "@/services/battle";

interface Props {
  state: BattleState;
  selectedId: string;
  onSelect: (id: string) => void;
  onConfirm: () => void;
}

export function ActionPanel({ state, selectedId, onSelect, onConfirm }: Props) {
  const selected = state.recommended.find((a) => a.id === selectedId) ?? state.recommended[0];

  return (
    <div className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="p-5 border-b border-border/40 bg-gradient-to-r from-electric/5 via-purple/5 to-transparent">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="size-8 rounded-lg bg-brand-gradient grid place-items-center [background-size:200%_100%] animate-gradient-flow">
              <Brain className="size-4 text-white" />
            </div>
            <div>
              <p className="font-semibold text-sm">Recommended moves</p>
              <p className="text-[10px] text-muted-foreground">
                {state.search_stats.iterations} iter · {state.search_stats.nodes_created} nodes ·
                {" "}
                {formatPercent(state.search_stats.cache_hit_rate, 1)} cache hit
              </p>
            </div>
          </div>
          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded">
            {Math.round(state.search_stats.iterations_per_sec)} iter/s
          </span>
        </div>
      </div>

      {/* Options */}
      <div className="p-3 space-y-2 overflow-y-auto flex-1">
        {state.recommended.map((a) => (
          <ActionRow key={a.id} action={a} selected={selected.id === a.id} onClick={() => onSelect(a.id)} />
        ))}
      </div>

      {/* Selected detail */}
      <SelectedDetail action={selected} />

      {/* Confirm */}
      <div className="p-4 border-t border-border/40 bg-background/30">
        <Button onClick={onConfirm} variant="gradient" size="lg" className="w-full font-semibold">
          Confirm move
          <ArrowRight className="size-5" />
        </Button>
      </div>
    </div>
  );
}

function ActionRow({ action, selected, onClick }: { action: BattleAction; selected: boolean; onClick: () => void }) {
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ x: 2 }}
      className={cn(
        "relative w-full overflow-hidden rounded-xl border p-3 text-left transition-colors group",
        selected
          ? "border-electric/40 bg-electric/5"
          : "border-border/40 bg-background/30 hover:border-border",
      )}
    >
      <div
        className="absolute inset-y-0 left-0 bg-brand-gradient/15 transition-all"
        style={{ width: `${action.visit_share * 100}%` }}
      />
      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-sm truncate">{action.label}</p>
          <p className="text-[11px] text-muted-foreground line-clamp-1 mt-0.5">{action.description}</p>
          <div className="flex items-center gap-2 mt-2 text-[10px] text-muted-foreground">
            <span className="font-mono tabular-nums">{action.visits} visits</span>
            <span>·</span>
            <span className="font-mono tabular-nums">{formatPercent(action.visit_share, 0)}</span>
          </div>
        </div>
        <div className="text-right shrink-0">
          <p className={cn("text-lg font-bold tabular-nums", selected ? "text-electric" : "text-foreground/80")}>
            {formatPercent(action.win_probability, 0)}
          </p>
          <p className="text-[9px] text-muted-foreground uppercase tracking-wider">Win</p>
        </div>
      </div>
    </motion.button>
  );
}

function SelectedDetail({ action }: { action: BattleAction }) {
  return (
    <div className="border-t border-border/40 p-4 space-y-3 bg-background/20">
      <div className="flex flex-wrap gap-2">
        <StatBadge label="Q value" value={action.q_value.toFixed(2)} accent="purple" />
        <StatBadge label="Prior" value={action.prior.toFixed(2)} accent="electric" />
        <StatBadge label="Prize swing" value={action.expected_prize_swing.toFixed(1)} accent={action.expected_prize_swing >= 0 ? "emerald" : "default"} />
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5 flex items-center gap-1">
          <Target className="size-3" />
          Principal variation
        </p>
        <ol className="space-y-1.5">
          {action.principal_variation.slice(0, 4).map((pv, i) => (
            <li key={i} className="flex items-start gap-2 text-xs text-foreground/80">
              <span className="font-mono text-muted-foreground shrink-0">{i + 1}.</span>
              <span className="leading-relaxed">{pv}</span>
            </li>
          ))}
        </ol>
      </div>
      <div>
        <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
          <span>Confidence</span>
          <span className="font-mono">{formatPercent(action.visit_share, 0)}</span>
        </div>
        <Progress value={action.visit_share * 100} />
      </div>
    </div>
  );
}
