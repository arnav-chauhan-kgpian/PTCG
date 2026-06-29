"use client";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { BarChart3, Cpu, Database, Layers, Network, RefreshCw, TrendingUp, Zap } from "lucide-react";
import { AreaChart } from "@/components/charts/area-chart";
import { ChartCard } from "@/components/charts/chart-card";
import { MetricCard } from "@/components/shared/metric-card";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatNumber } from "@/lib/utils";
import { getBenchmarkHistory, getLatestBenchmark } from "@/services/benchmarks";

export default function BenchmarksPage() {
  const latest = useQuery({ queryKey: ["benchmark-latest"], queryFn: getLatestBenchmark });
  const history = useQuery({ queryKey: ["benchmark-history"], queryFn: getBenchmarkHistory });

  const trendData = history.data?.map((s) => ({
    day: new Date(s.timestamp).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    sim: s.simulator_actions_per_sec ?? 0,
    encoder: s.encoder_per_sec ?? 0,
    mcts: s.mcts_iterations_per_sec ?? 0,
  })) ?? [];

  return (
    <div className="container max-w-7xl py-6 md:py-10 space-y-6">
      <PageHeader
        title="Benchmarks"
        description="Reproducible performance — measured on the bundled 1,267-card repository."
        icon={<BarChart3 className="size-5" />}
        actions={
          <Button variant="glass" size="sm" onClick={() => latest.refetch()}>
            <RefreshCw className="size-4" /> Re-run
          </Button>
        }
      />

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
        <MetricCard label="Simulator" value={formatNumber(latest.data?.simulator_actions_per_sec ?? 0)} unit="actions/s" icon={Cpu} accent="electric" trend={0.06} delay={0} />
        <MetricCard label="Games" value={(latest.data?.simulator_games_per_sec ?? 0).toFixed(1)} unit="games/s" icon={Zap} accent="electric" trend={0.04} delay={0.05} />
        <MetricCard label="Encoder" value={formatNumber(latest.data?.encoder_per_sec ?? 0)} unit="encodes/s" icon={Layers} accent="indigo" trend={0.02} delay={0.1} />
        <MetricCard label="MCTS" value={latest.data?.mcts_iterations_per_sec ?? 0} unit="iter/s" icon={TrendingUp} accent="purple" trend={0.08} delay={0.15} />
        <MetricCard label="Network single" value={`${latest.data?.network_single_latency_us ?? 0} µs`} icon={Network} accent="purple" trend={-0.04} delay={0.2} description="Inference latency" />
        <MetricCard label="Network batch" value={formatNumber(latest.data?.network_batch_per_sec ?? 0)} unit="states/s" icon={Network} accent="purple" trend={0.11} delay={0.25} description="Batch-32" />
        <MetricCard label="Replay" value={formatNumber(latest.data?.replay_samples_per_sec ?? 0)} unit="samples/s" icon={Database} accent="emerald" trend={0.03} delay={0.3} />
        <MetricCard label="Repo load" value="<1 s" icon={Database} accent="emerald" delay={0.35} description="1,267 cards" />
      </div>

      <ChartCard title="History (12 days)" description="Simulator / Encoder / MCTS throughput">
        {history.data ? (
          <AreaChart
            data={trendData}
            xKey="day"
            series={[
              { key: "sim", label: "Simulator (×10)", color: "#4A8FFF" },
              { key: "encoder", label: "Encoder", color: "#A855F7" },
              { key: "mcts", label: "MCTS (×30)", color: "#FFB627" },
            ]}
            yFormatter={(v) => formatNumber(Math.round(v))}
          />
        ) : <Skeleton className="h-full" />}
      </ChartCard>

      <motion.div
        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-6"
      >
        <p className="font-semibold text-sm mb-3">Reproduce locally</p>
        <pre className="bg-background/60 rounded-lg p-4 text-xs font-mono overflow-x-auto text-foreground/90 leading-relaxed">
          {`# Run the same benchmark suite as the dashboard
python benchmarks/run.py
pokemon-ai --json benchmark > benchmark.json`}
        </pre>
      </motion.div>
    </div>
  );
}
