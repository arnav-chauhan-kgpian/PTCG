"use client";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Bot, Pause, Play, RotateCcw, Zap } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";
import { ActionPanel } from "@/components/battle/action-panel";
import { BattleLog } from "@/components/battle/battle-log";
import { BattleSidePanel } from "@/components/battle/battle-side";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getDemoBattleState } from "@/services/battle";

export default function BattlePage() {
  const battle = useQuery({ queryKey: ["battle"], queryFn: getDemoBattleState });
  const [selectedId, setSelectedId] = React.useState<string>("");
  const [autoplay, setAutoplay] = React.useState(false);

  React.useEffect(() => {
    if (battle.data && !selectedId) setSelectedId(battle.data.recommended[0].id);
  }, [battle.data, selectedId]);

  if (!battle.data) {
    return (
      <div className="container max-w-7xl py-6 md:py-10 space-y-4">
        <Skeleton className="h-12 w-1/3" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  const onConfirm = () => {
    const action = battle.data.recommended.find((a) => a.id === selectedId);
    toast.success(`Move confirmed`, {
      description: action?.label,
      action: { label: "Undo", onClick: () => {} },
    });
  };

  return (
    <div className="container max-w-7xl py-6 md:py-10 space-y-6">
      <PageHeader
        title="Battle Arena"
        description={`Turn ${battle.data.turn} · ${battle.data.current_player === "you" ? "Your turn — agent is deliberating" : "Opponent's turn"}`}
        icon={<Bot className="size-5" />}
        actions={
          <div className="flex gap-2">
            <Badge variant="success" className="gap-1.5">
              <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Live
            </Badge>
            <Button variant="glass" size="sm" onClick={() => setAutoplay((s) => !s)}>
              {autoplay ? <Pause className="size-4" /> : <Play className="size-4" />}
              {autoplay ? "Pause" : "Autoplay"}
            </Button>
            <Button variant="glass" size="sm" onClick={() => toast.info("Match reset (mock)")}>
              <RotateCcw className="size-4" />
              Reset
            </Button>
          </div>
        }
      />

      {/* Board */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4">
        <div className="space-y-4">
          <BattleSidePanel
            side={battle.data.opponent}
            reversed
            isTurn={battle.data.current_player === "opponent"}
          />
          <TurnDivider turn={battle.data.turn} />
          <BattleSidePanel
            side={battle.data.you}
            isTurn={battle.data.current_player === "you"}
          />
        </div>

        <div className="space-y-4 flex flex-col">
          <ActionPanel
            state={battle.data}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onConfirm={onConfirm}
          />
        </div>
      </div>

      {/* Bottom strip: log + search summary */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4">
        <BattleLog log={battle.data.log} />
        <SearchSummary state={battle.data} />
      </div>
    </div>
  );
}

function TurnDivider({ turn }: { turn: number }) {
  return (
    <div className="relative flex items-center gap-3">
      <div className="flex-1 h-px bg-gradient-to-r from-transparent via-electric/40 to-transparent" />
      <span className="inline-flex items-center gap-2 rounded-full glass px-3 py-1 text-xs">
        <Zap className="size-3 text-electric" />
        Turn {turn}
      </span>
      <div className="flex-1 h-px bg-gradient-to-r from-transparent via-purple/40 to-transparent" />
    </div>
  );
}

function SearchSummary({ state }: { state: Awaited<ReturnType<typeof getDemoBattleState>> }) {
  return (
    <div className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-5">
      <p className="font-semibold text-sm mb-3">Search statistics</p>
      <dl className="grid grid-cols-2 gap-3 text-xs">
        <Stat label="Iterations" value={state.search_stats.iterations} />
        <Stat label="Nodes" value={state.search_stats.nodes_created} />
        <Stat label="Avg branching" value={state.search_stats.avg_branching.toFixed(1)} />
        <Stat label="PV depth" value={state.search_stats.pv_depth} />
        <Stat label="Cache hit" value={`${Math.round(state.search_stats.cache_hit_rate * 100)}%`} />
        <Stat label="Iter / s" value={state.search_stats.iterations_per_sec} />
      </dl>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-lg border border-border/30 bg-background/30 p-2.5">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="font-mono font-bold text-sm tabular-nums mt-0.5">{value}</p>
    </div>
  );
}
