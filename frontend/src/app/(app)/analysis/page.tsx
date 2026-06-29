"use client";
import { motion } from "framer-motion";
import { ArrowRight, Brain, Microscope, Play } from "lucide-react";
import * as React from "react";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

const moves = [
  { rank: 1, label: "Attack — Burning Darkness", visits: 487, share: 0.61, value: 0.74, prior: 0.42 },
  { rank: 2, label: "Play — Iono", visits: 198, share: 0.25, value: 0.61, prior: 0.18 },
  { rank: 3, label: "Use ability — Quick Search", visits: 78, share: 0.10, value: 0.58, prior: 0.16 },
  { rank: 4, label: "Retreat to Pidgeot", visits: 26, share: 0.04, value: 0.42, prior: 0.10 },
];

export default function AnalysisPage() {
  return (
    <div className="container max-w-7xl py-6 md:py-10 space-y-6">
      <PageHeader
        title="Game Analysis"
        description="Explain any decision the agent made. Upload a state or replay one from the database."
        icon={<Microscope className="size-5" />}
        actions={
          <div className="flex gap-2">
            <Button variant="glass" size="sm"><Play className="size-4" /> Load demo</Button>
            <Button variant="gradient" size="sm">Analyze new state <ArrowRight className="size-4" /></Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4">
        <motion.div
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="font-semibold text-sm">Top moves (visit count)</p>
              <p className="text-xs text-muted-foreground">Turn 7 · Your move · 789 iterations in 1.3s</p>
            </div>
            <Badge variant="info">Heuristic + Neural</Badge>
          </div>

          <ul className="space-y-2">
            {moves.map((m) => (
              <li key={m.rank} className="relative overflow-hidden rounded-xl border border-border/40 bg-background/30 p-4">
                <div className="absolute inset-y-0 left-0 bg-brand-gradient/15" style={{ width: `${m.share * 100}%` }} />
                <div className="relative grid grid-cols-[auto_1fr_repeat(4,minmax(0,80px))] gap-4 items-center text-xs">
                  <span className="font-mono text-muted-foreground">#{m.rank}</span>
                  <span className="font-semibold text-sm truncate">{m.label}</span>
                  <DataPoint label="Visits" value={m.visits} />
                  <DataPoint label="Share" value={`${Math.round(m.share * 100)}%`} />
                  <DataPoint label="Q" value={m.value.toFixed(2)} />
                  <DataPoint label="P" value={m.prior.toFixed(2)} />
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-6 grid md:grid-cols-2 gap-4">
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">Principal variation</p>
              <ol className="space-y-1 text-sm">
                <li>1. <strong>Burning Darkness</strong> on Gardevoir ex — predicted KO</li>
                <li>2. Opponent promotes Kirlia</li>
                <li>3. Boss's Orders → pull Ralts to active</li>
                <li>4. Charizard attacks for game</li>
              </ol>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">Expected outcomes</p>
              <ul className="text-sm space-y-1.5">
                <li className="flex justify-between"><span>Expected prize swing</span><span className="font-mono font-bold text-emerald-400">+2.0</span></li>
                <li className="flex justify-between"><span>Expected KOs</span><span className="font-mono font-bold">2</span></li>
                <li className="flex justify-between"><span>Confidence</span><span className="font-mono font-bold text-electric">74%</span></li>
              </ul>
            </div>
          </div>
        </motion.div>

        <div className="space-y-4">
          <motion.div
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-5"
          >
            <p className="font-semibold text-sm mb-3">Search summary</p>
            <ul className="text-xs space-y-2">
              <Row label="Iterations" value="789" />
              <Row label="Nodes" value="1,421" />
              <Row label="Avg branching" value="6.2" />
              <Row label="PV depth" value="4" />
              <Row label="Cache hit" value="78%" />
              <Row label="Iter / s" value="359" />
            </ul>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
            className="rounded-2xl border border-electric/30 bg-electric/5 backdrop-blur-xl p-5"
          >
            <div className="flex items-center gap-2 mb-2">
              <div className="size-8 rounded-lg bg-brand-gradient grid place-items-center [background-size:200%_100%] animate-gradient-flow">
                <Brain className="size-4 text-white" />
              </div>
              <p className="font-semibold text-sm">Neural value</p>
            </div>
            <p className="text-3xl font-bold font-display text-electric tabular-nums">0.74</p>
            <p className="text-xs text-muted-foreground mt-1">From the perspective of the current player.</p>
            <Progress value={74} className="mt-3" />
          </motion.div>
        </div>
      </div>
    </div>
  );
}

function DataPoint({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="text-right">
      <p className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="font-mono font-bold tabular-nums">{value}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <li className="flex items-center justify-between rounded-lg border border-border/30 bg-background/30 px-3 py-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-semibold tabular-nums">{value}</span>
    </li>
  );
}
