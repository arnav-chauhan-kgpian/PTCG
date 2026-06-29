"use client";
import { motion } from "framer-motion";
import { Activity, Brain, ChevronRight, Cpu } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export function DemoSection() {
  return (
    <section id="demo" className="relative py-24 md:py-32 overflow-hidden">
      <div className="container">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <span className="inline-flex items-center gap-1.5 rounded-full glass px-3 py-1 text-xs font-medium uppercase tracking-wider mb-4">
              Live Demo
            </span>
            <h2 className="font-display font-bold text-3xl md:text-5xl tracking-tight">
              Watch the agent <span className="text-gradient">think</span>
            </h2>
            <p className="mt-4 text-muted-foreground leading-relaxed">
              Every decision shows its top moves, visit counts, value estimates, and principal
              variation. Built to be explainable, not a black box.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row gap-3">
              <Button asChild variant="gradient" size="lg">
                <Link href="/battle">Open Battle Arena <ChevronRight className="size-4" /></Link>
              </Button>
              <Button asChild variant="glass" size="lg">
                <Link href="/analysis">Game Analysis</Link>
              </Button>
            </div>
            <div className="mt-8 grid grid-cols-3 gap-3">
              {[
                { icon: Cpu, label: "MCTS" },
                { icon: Brain, label: "Neural" },
                { icon: Activity, label: "Self-play" },
              ].map((f, i) => (
                <div key={i} className="rounded-xl border border-border/40 bg-card/40 backdrop-blur p-3 text-center">
                  <f.icon className="size-4 mx-auto text-electric" />
                  <p className="text-xs mt-1 font-medium">{f.label}</p>
                </div>
              ))}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="relative"
          >
            <div className="absolute -inset-8 bg-brand-gradient blur-3xl opacity-20 rounded-3xl [background-size:200%_100%] animate-gradient-flow" />
            <div className="relative rounded-2xl border border-border/60 bg-card/60 backdrop-blur-2xl p-6 shadow-2xl perspective-1000">
              <DecisionMock />
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function DecisionMock() {
  const options = [
    { label: "Attack — Burning Darkness", visits: 487, share: 0.61, value: 0.74, primary: true },
    { label: "Play — Iono", visits: 198, share: 0.25, value: 0.61 },
    { label: "Use Ability — Quick Search", visits: 78, share: 0.10, value: 0.58 },
    { label: "Retreat", visits: 26, share: 0.04, value: 0.42 },
  ];
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Turn 7 · Your move</p>
          <p className="text-sm mt-0.5">Charizard ex (230/330) vs Gardevoir ex (180/310)</p>
        </div>
        <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded">789 iter · 1.3s</span>
      </div>
      <div className="space-y-2">
        {options.map((o, i) => (
          <motion.div
            key={o.label}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 + i * 0.08 }}
            className={`relative overflow-hidden rounded-lg border p-3 ${
              o.primary ? "border-electric/40 bg-electric/5" : "border-border/40 bg-background/30"
            }`}
          >
            <div className={`absolute inset-y-0 left-0 bg-brand-gradient/30 ${o.primary ? "opacity-80" : "opacity-40"}`}
                  style={{ width: `${o.share * 100}%` }} />
            <div className="relative flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{o.label}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  {o.visits} visits · {(o.share * 100).toFixed(0)}% of search
                </p>
              </div>
              <div className="text-right shrink-0">
                <p className="text-sm font-bold text-electric tabular-nums">{(o.value * 100).toFixed(0)}%</p>
                <p className="text-[10px] text-muted-foreground">win prob</p>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
      <div className="pt-2 border-t border-border/40">
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Principal variation</p>
        <p className="text-xs font-mono text-foreground/80 leading-relaxed">
          Burning Darkness → promote Kirlia → Boss's → KO Ralts
        </p>
      </div>
    </div>
  );
}
