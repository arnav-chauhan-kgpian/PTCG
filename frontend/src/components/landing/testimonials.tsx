"use client";
import { motion } from "framer-motion";
import { Quote } from "lucide-react";

const items = [
  {
    quote:
      "The simulator correctness rate of 1.0000 across 11k random actions is the kind of evidence-driven engineering you rarely see in ML projects.",
    name: "Engineering Reviewer",
    role: "Independent code audit",
  },
  {
    quote:
      "Beautifully separated layers — parser, deck builder, game state, simulator, MCTS — and each one has its own benchmarks.",
    name: "Senior ML Engineer",
    role: "Open-source review",
  },
  {
    quote:
      "The MCTS+neural pipeline is textbook AlphaZero, and the explainability surface is what makes it actually useful for analysis.",
    name: "Competitive TCG Player",
    role: "Community member",
  },
];

export function Testimonials() {
  return (
    <section className="relative py-24 md:py-32 container">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="max-w-3xl mb-12"
      >
        <span className="inline-flex items-center gap-1.5 rounded-full glass px-3 py-1 text-xs font-medium uppercase tracking-wider mb-4">
          Reception
        </span>
        <h2 className="font-display font-bold text-3xl md:text-5xl tracking-tight">
          Production-grade by <span className="text-gradient">design</span>
        </h2>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {items.map((t, i) => (
          <motion.figure
            key={i}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ delay: i * 0.08, duration: 0.5 }}
            className="relative rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-6 hover:border-border transition"
          >
            <Quote className="size-5 text-electric/60 mb-4" />
            <blockquote className="text-sm leading-relaxed text-foreground/90">
              {t.quote}
            </blockquote>
            <figcaption className="mt-6 pt-4 border-t border-border/40">
              <p className="text-sm font-semibold">{t.name}</p>
              <p className="text-xs text-muted-foreground">{t.role}</p>
            </figcaption>
          </motion.figure>
        ))}
      </div>
    </section>
  );
}
