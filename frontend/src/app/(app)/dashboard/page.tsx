"use client";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Activity, BarChart3, Brain, CheckCircle2, Cpu, Database, FlaskConical,
  Gamepad2, GitBranch, LayoutDashboard, Sparkles, TrendingUp, Trophy,
} from "lucide-react";
import { AreaChart } from "@/components/charts/area-chart";
import { ChartCard } from "@/components/charts/chart-card";
import { MetricCard } from "@/components/shared/metric-card";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber, formatPercent, formatRelativeTime } from "@/lib/utils";
import { getDashboardSummary } from "@/services/dashboard";
import { getTrainingMetrics } from "@/services/training";

export default function DashboardPage() {
  const dash = useQuery({ queryKey: ["dashboard"], queryFn: getDashboardSummary, refetchInterval: 30_000 });
  const train = useQuery({ queryKey: ["training"], queryFn: getTrainingMetrics, refetchInterval: 60_000 });

  return (
    <div className="container max-w-7xl py-6 md:py-10 space-y-8">
      <PageHeader
        title="Dashboard"
        description="Live overview of training, simulator fidelity, and search performance."
        icon={<LayoutDashboard className="size-5" />}
        actions={
          <Button variant="gradient" size="sm">
            <Sparkles className="size-4" /> New Experiment
          </Button>
        }
      />

      {/* Metric grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
        <MetricCard
          label="Games Played" value={formatNumber(dash.data?.games_played ?? 0)}
          icon={Gamepad2} trend={0.124} trendLabel="vs last week"
          accent="electric" loading={dash.isLoading} delay={0.0}
        />
        <MetricCard
          label="Win Rate" value={dash.data ? formatPercent(dash.data.win_rate, 1) : "—"}
          icon={Trophy} trend={0.048} trendLabel="vs prev checkpoint"
          accent="gold" loading={dash.isLoading} delay={0.05}
        />
        <MetricCard
          label="Simulator Fidelity" value={dash.data ? formatPercent(dash.data.simulator_fidelity, 1) : "—"}
          icon={CheckCircle2} trend={0.034} trendLabel="P1 mechanics"
          accent="emerald" loading={dash.isLoading} delay={0.1}
        />
        <MetricCard
          label="MCTS Speed" value={dash.data?.mcts_speed ?? "—"} unit="iter/s"
          icon={Cpu} trend={0.02} trendLabel="real card states"
          accent="purple" loading={dash.isLoading} delay={0.15}
        />
        <MetricCard
          label="Training Progress" value={dash.data ? formatPercent(dash.data.training_progress, 0) : "—"}
          icon={Activity} trend={0.07}
          accent="indigo" loading={dash.isLoading} delay={0.2}
        />
        <MetricCard
          label="Cache Hit Rate" value={dash.data ? formatPercent(dash.data.cache_hit_rate, 1) : "—"}
          icon={Database} trend={0.018}
          accent="electric" loading={dash.isLoading} delay={0.25}
        />
        <MetricCard
          label="Test Coverage" value={dash.data ? formatPercent(dash.data.coverage, 0) : "—"}
          icon={FlaskConical} trend={0.005}
          accent="emerald" loading={dash.isLoading} delay={0.3}
        />
        <MetricCard
          label="Tests Passing" value={formatNumber(dash.data?.tests_passing ?? 0)}
          icon={CheckCircle2} description="ruff-clean · 4 skipped"
          accent="emerald" loading={dash.isLoading} delay={0.35}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ChartCard
          title="Training loss"
          description="Total / policy / value (last 60 steps)"
          action={<Badge variant="info">Live</Badge>}
        >
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
          ) : (
            <Skeleton className="h-full" />
          )}
        </ChartCard>

        <ChartCard
          title="Arena Elo"
          description="Candidate vs current best, per round"
          action={<Badge variant="gradient">+312 vs init</Badge>}
        >
          {train.data ? (
            <AreaChart
              data={train.data.arena}
              xKey="round"
              series={[{ key: "elo", label: "Elo", color: "#FFB627" }]}
              yFormatter={(v) => Math.round(v).toString()}
              xFormatter={(v) => `R${v}`}
            />
          ) : (
            <Skeleton className="h-full" />
          )}
        </ChartCard>
      </div>

      {/* Activity + system health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          className="lg:col-span-2 rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-sm">Recent activity</h3>
              <p className="text-xs text-muted-foreground">Last training round events</p>
            </div>
            <Button variant="ghost" size="sm">View all</Button>
          </div>
          <ul className="space-y-3">
            {dash.data?.recent_activity.map((a) => (
              <li key={a.id} className="flex items-start gap-3 p-3 rounded-lg border border-border/30 bg-background/30">
                <ActivityIcon kind={a.kind} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">{a.message}</p>
                  <p className="text-xs text-muted-foreground">{formatRelativeTime(a.timestamp)}</p>
                </div>
                <Badge variant="outline" className="shrink-0 capitalize text-[10px]">{a.kind}</Badge>
              </li>
            ))}
          </ul>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
          className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-6 space-y-4"
        >
          <div>
            <h3 className="font-semibold text-sm">Current Model</h3>
            <p className="text-xs text-muted-foreground">Active checkpoint</p>
          </div>
          <div className="rounded-xl border border-electric/30 bg-electric/5 p-4 flex items-start gap-3">
            <div className="size-10 rounded-lg bg-brand-gradient grid place-items-center [background-size:200%_100%] animate-gradient-flow">
              <Brain className="size-5 text-white" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-mono text-sm font-semibold">{dash.data?.current_model ?? "—"}</p>
              <p className="text-xs text-muted-foreground mt-0.5">Promoted 22m ago</p>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <SystemStat icon={Activity} label="Uptime" value={`${Math.round((dash.data?.system_health.uptime_s ?? 0) / 60)}m`} />
            <SystemStat icon={GitBranch} label="Branch" value="main" />
            <SystemStat icon={BarChart3} label="Bench" value={dash.data ? formatRelativeTime(dash.data.latest_benchmark_at) : "—"} />
            <SystemStat icon={TrendingUp} label="Replay" value={`${(train.data?.replay_size ?? 0).toLocaleString()}`} />
          </div>
        </motion.div>
      </div>
    </div>
  );
}

function SystemStat({ icon: Icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/40 bg-background/30 p-3">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        <Icon className="size-3" />
        <span className="text-[10px] uppercase tracking-wider">{label}</span>
      </div>
      <p className="text-sm font-semibold mt-1 truncate">{value}</p>
    </div>
  );
}

function ActivityIcon({ kind }: { kind: string }) {
  const map: Record<string, { icon: any; bg: string }> = {
    training: { icon: Activity, bg: "bg-electric/10 text-electric" },
    promotion: { icon: Trophy, bg: "bg-gold/10 text-gold-light" },
    benchmark: { icon: BarChart3, bg: "bg-purple/10 text-purple-light" },
    checkpoint: { icon: GitBranch, bg: "bg-indigo/10 text-indigo-light" },
    validation: { icon: CheckCircle2, bg: "bg-emerald-500/10 text-emerald-400" },
  };
  const cfg = map[kind] ?? map.training;
  return (
    <div className={`size-8 rounded-lg grid place-items-center shrink-0 ${cfg.bg}`}>
      <cfg.icon className="size-4" />
    </div>
  );
}
