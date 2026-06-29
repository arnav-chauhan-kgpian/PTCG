"use client";
import { motion } from "framer-motion";
import { ArrowDown } from "lucide-react";

const layers = [
  { name: "Card Knowledge Layer", desc: "parser · models · effect engine · relationship graph", color: "from-electric/50 to-electric/10" },
  { name: "Deck Layer", desc: "analysis · archetype · synergy · automatic builder", color: "from-indigo/50 to-indigo/10" },
  { name: "Game State + Feature Encoder", desc: "Immutable Pydantic · 741-dim vector · SHA-256 hashing", color: "from-purple/50 to-purple/10" },
  { name: "Simulator (1.0 correctness)", desc: "rules engine · 17 trainers · 8 abilities · tools · stadiums", color: "from-purple/50 to-electric/10" },
  { name: "MCTS + Neural Inference", desc: "UCT/PUCT · transposition · self-play · replay buffer", color: "from-electric/50 to-purple/10" },
  { name: "Training Pipeline", desc: "AlphaZero loop · arena · promotion · experiments", color: "from-gold/50 to-purple/10" },
  { name: "Competition Mode", desc: "Agent · REST API · CLI · Docker · CI/CD", color: "from-gold/50 to-gold/10" },
];

export function ArchitectureSection() {
  return (
    <section id="architecture" className="relative py-24 md:py-32 overflow-hidden">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-border to-transparent" />
      <div className="container">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <span className="inline-flex items-center gap-1.5 rounded-full glass px-3 py-1 text-xs font-medium uppercase tracking-wider mb-4">
            Architecture
          </span>
          <h2 className="font-display font-bold text-3xl md:text-5xl tracking-tight">
            Built as a <span className="text-gradient">layered system</span>
          </h2>
          <p className="mt-4 text-muted-foreground max-w-2xl mx-auto">
            Each layer composes upward. Phases were shipped sequentially, every gate has tests and benchmarks.
          </p>
        </motion.div>

        <div className="max-w-3xl mx-auto space-y-3">
          {layers.map((l, i) => (
            <motion.div
              key={l.name}
              initial={{ opacity: 0, x: -16 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
              className="group"
            >
              <div className="relative overflow-hidden rounded-xl border border-border/40 bg-card/40 backdrop-blur p-5 hover:border-border transition">
                <div className={`absolute inset-0 bg-gradient-to-r ${l.color} opacity-30 group-hover:opacity-50 transition`} />
                <div className="relative flex items-center justify-between gap-3">
                  <div>
                    <h3 className="font-display font-semibold text-base">{l.name}</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">{l.desc}</p>
                  </div>
                  <span className="font-mono text-xs text-muted-foreground tabular-nums">
                    L{i + 1}
                  </span>
                </div>
              </div>
              {i < layers.length - 1 && (
                <div className="flex justify-center py-1.5 text-muted-foreground/50">
                  <ArrowDown className="size-4" />
                </div>
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
