"use client";
import { motion } from "framer-motion";
import { ArrowRight, Play, Sparkles } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export function Hero() {
  return (
    <section className="relative isolate pt-32 pb-24 md:pt-44 md:pb-32 overflow-hidden">
      {/* mesh gradient backdrop */}
      <div className="absolute inset-0 -z-10 mesh-bg" />
      {/* animated grid */}
      <div className="absolute inset-0 -z-10 grid-bg opacity-30 [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_70%)]" />
      {/* floating particles */}
      <FloatingOrbs />

      <div className="container relative">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="flex flex-col items-center text-center max-w-4xl mx-auto"
        >
          <Link
            href="#features"
            className="inline-flex items-center gap-2 rounded-full glass px-4 py-1.5 text-xs font-medium uppercase tracking-wider mb-8 hover:bg-white/10 transition-colors group"
          >
            <span className="size-1.5 rounded-full bg-electric animate-pulse" />
            v1.0 — 1,065 tests · 90% coverage · 100% simulator correctness
            <ArrowRight className="size-3 group-hover:translate-x-0.5 transition-transform" />
          </Link>

          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.05 }}
            className="font-display font-bold text-5xl md:text-7xl lg:text-8xl tracking-tight leading-[1.05]"
          >
            <span className="block">An AlphaZero-class</span>
            <span className="block text-gradient pb-1">Pokémon TCG AI</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.15 }}
            className="mt-6 max-w-2xl text-base md:text-lg text-muted-foreground leading-relaxed"
          >
            A production-grade framework that learns, plays, and explains the Pokémon Trading Card Game.
            Train. Analyze. Battle. Learn — all powered by neural MCTS over 1,267 real cards.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.25 }}
            className="mt-10 flex flex-col sm:flex-row items-center gap-3"
          >
            <Button asChild variant="gradient" size="xl" className="font-semibold shadow-lg shadow-purple/30">
              <Link href="/dashboard">
                Open Dashboard
                <ArrowRight className="size-5" />
              </Link>
            </Button>
            <Button asChild variant="glass" size="xl" className="font-semibold">
              <Link href="/battle">
                <Play className="size-5 fill-current" />
                Watch Live Battle
              </Link>
            </Button>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-8 text-center"
          >
            {[
              { value: "1.0000", label: "Simulator correctness" },
              { value: "87.5%", label: "Attack fidelity" },
              { value: "10.3k", label: "Actions / sec" },
              { value: "359", label: "MCTS iter / sec" },
            ].map((s) => (
              <div key={s.label}>
                <div className="text-2xl md:text-3xl font-bold font-display text-gradient">{s.value}</div>
                <div className="text-[10px] md:text-xs uppercase tracking-wider text-muted-foreground mt-1">
                  {s.label}
                </div>
              </div>
            ))}
          </motion.div>
        </motion.div>
      </div>

      {/* glow underneath */}
      <div className="absolute left-1/2 -translate-x-1/2 -bottom-40 -z-10 size-[600px] rounded-full bg-electric/20 blur-3xl opacity-50" />
      <div className="absolute left-1/3 -bottom-20 -z-10 size-[300px] rounded-full bg-purple/30 blur-3xl opacity-40" />
    </section>
  );
}

function FloatingOrbs() {
  const orbs = [
    { size: 320, top: "10%", left: "5%", color: "bg-electric", delay: 0 },
    { size: 240, top: "60%", right: "8%", color: "bg-purple", delay: 0.8 },
    { size: 180, top: "30%", right: "30%", color: "bg-gold", delay: 1.6 },
  ];
  return (
    <div className="absolute inset-0 -z-10 overflow-hidden pointer-events-none">
      {orbs.map((o, i) => (
        <motion.div
          key={i}
          className={`absolute rounded-full ${o.color} blur-3xl opacity-20`}
          style={{ width: o.size, height: o.size, top: o.top, left: o.left, right: o.right }}
          animate={{ y: [0, -24, 0], x: [0, 16, 0] }}
          transition={{ duration: 12 + i * 2, repeat: Infinity, delay: o.delay, ease: "easeInOut" }}
        />
      ))}
    </div>
  );
}
