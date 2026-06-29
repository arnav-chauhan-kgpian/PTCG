"use client";
import { useQuery } from "@tanstack/react-query";
import { Activity, BarChart3, Cpu, Database, GitBranch, TrendingUp, Trophy } from "lucide-react";
import { AreaChart } from "@/components/charts/area-chart";
import { ChartCard } from "@/components/charts/chart-card";
import { MetricCard } from "@/components/shared/metric-card";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber, formatPercent } from "@/lib/utils";
import { getTrainingMetrics } from "@/services/training";

export default function TrainingPage() {
  const train = useQuery({ queryKey: ["training"], queryFn: getTrainingMetrics, refetchInterval: 30_000 });

  const last = train.data?.steps.at(-1);
  const lastArena = train.data?.arena.at(-1);

  return (
    <div className="container max-w-7xl py-6 md:py-10 space-y-6">
      <PageHeader
        title="Training"
        description="Live AlphaZero loop telemetry — self-play, training steps, arena, promotion."
        icon={<Activity className="size-5" />}
        actions={<Badge variant="success" className="gap-1.5"><span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" /> Active</Badge>}
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Total loss" value={last?.total_loss.toFixed(3) ?? "—"} icon={TrendingUp} trend={-0.18} accent="electric" />
        <MetricCard label="Policy loss" value={last?.policy_loss.toFixed(3) ?? "—"} icon={TrendingUp} trend={-0.12} accent="purple" />
        <MetricCard label="Value loss" value={last?.value_loss.toFixed(3) ?? "—"} icon={TrendingUp} trend={-0.21} accent="indigo" />
        <MetricCard label="Arena Elo" value={lastArena?.elo ?? "—"} icon={Trophy} trend={0.08} accent="gold" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard title="Loss curves" description="Total / Policy / Value">
          {train.data ? (
            <AreaChart
              data={train.data.steps}
              xKey="step"
              series={[
                { key: "total_loss", label: "Total", color: "#5E5CFF" },
                { key: "policy_loss", label: "Policy", color: "#4A8FFF" },
                { key: "value_loss", label: "Value", color: "#A855F7" },
              ]}
              yFormatter={(v) => v.toFixed(2)}
            />
          ) : <Skeleton className="h-full" />}
        </ChartCard>

        <ChartCard title="Arena win rate" description="Candidate score per round (chess-style)">
          {train.data ? (
            <AreaChart
              data={train.data.arena}
              xKey="round"
              series={[{ key: "win_rate", label: "Win rate", color: "#FFB627" }]}
              yFormatter={(v) => `${Math.round(v * 100)}%`}
              xFormatter={(v) => `R${v}`}
            />
          ) : <Skeleton className="h-full" />}
        </ChartCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="font-semibold text-sm">Promotion history</p>
              <p className="text-xs text-muted-foreground">Candidates that beat the gate</p>
            </div>
            <Badge variant="info">{train.data?.promotions.length} promoted</Badge>
          </div>
          <ul className="space-y-2">
            {train.data?.promotions.map((p) => (
              <li key={p.round} className="flex items-center justify-between rounded-lg border border-border/40 bg-background/30 p-3">
                <div className="flex items-center gap-3">
                  <div className="size-9 rounded-lg bg-gold/15 grid place-items-center">
                    <Trophy className="size-4 text-gold-light" />
                  </div>
                  <div>
                    <p className="font-semibold text-sm">Round {p.round}</p>
                    <p className="text-xs text-muted-foreground">{p.reason}</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Badge variant="success">{formatPercent(p.win_rate, 0)} win</Badge>
                  <Badge variant="gradient">{formatPercent(p.score, 0)} score</Badge>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-6 space-y-3">
          <p className="font-semibold text-sm">Runtime</p>
          <Row icon={Database} label="Replay size" value={formatNumber(train.data?.replay_size ?? 0)} />
          <Row icon={Cpu} label="Learning rate" value={(train.data?.learning_rate ?? 0).toExponential(1)} />
          <Row icon={BarChart3} label="Samples/sec" value={formatNumber(train.data?.throughput_samples_per_sec ?? 0)} />
          <Row icon={GitBranch} label="Latest checkpoint" value="ckpt_000048.pt" mono />
        </div>
      </div>
    </div>
  );
}

function Row({ icon: Icon, label, value, mono }: { icon: any; label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg border border-border/40 bg-background/30 p-3">
      <div className="flex items-center gap-2 min-w-0">
        <Icon className="size-4 text-muted-foreground shrink-0" />
        <span className="text-xs text-muted-foreground truncate">{label}</span>
      </div>
      <span className={`text-sm font-semibold tabular-nums ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}
