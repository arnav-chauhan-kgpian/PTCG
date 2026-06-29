"use client";
import { motion } from "framer-motion";

const metrics = [
  { label: "Simulator", value: "10,306", unit: "actions/s", glow: "from-electric/40 to-electric/0", color: "text-electric" },
  { label: "Encoder", value: "9,591", unit: "encodes/s", glow: "from-purple/40 to-purple/0", color: "text-purple-light" },
  { label: "MCTS", value: "359", unit: "iter/s", glow: "from-indigo/40 to-indigo/0", color: "text-indigo-light" },
  { label: "Network (batched)", value: "7,916", unit: "states/s", glow: "from-gold/40 to-gold/0", color: "text-gold-light" },
  { label: "Replay", value: "1.09M", unit: "samples/s", glow: "from-electric/40 to-electric/0", color: "text-electric" },
  { label: "Latency (single)", value: "916µs", unit: "/call", glow: "from-purple/40 to-purple/0", color: "text-purple-light" },
];

export function PerformanceSection() {
  return (
    <section id="performance" className="relative py-24 md:py-32 container">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="max-w-3xl"
      >
        <span className="inline-flex items-center gap-1.5 rounded-full glass px-3 py-1 text-xs font-medium uppercase tracking-wider mb-4">
          Performance
        </span>
        <h2 className="font-display font-bold text-3xl md:text-5xl tracking-tight">
          Measured on real cards.{" "}
          <span className="text-gradient">Reproducible.</span>
        </h2>
        <p className="mt-4 text-muted-foreground">
          Numbers from <code className="text-foreground bg-secondary/40 px-1.5 py-0.5 rounded text-xs">python benchmarks/run.py</code> on the bundled 1,267-card repository, CPU.
        </p>
      </motion.div>

      <div className="mt-12 grid grid-cols-2 md:grid-cols-3 gap-4">
        {metrics.map((m, i) => (
          <motion.div
            key={m.label}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ delay: i * 0.05, duration: 0.5 }}
            className="relative overflow-hidden rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-6 hover:border-border transition group"
          >
            <div className={`absolute -top-12 -right-12 size-48 rounded-full bg-gradient-radial opacity-50 blur-3xl ${m.glow}`} />
            <div className="relative">
              <p className="text-xs uppercase tracking-wider text-muted-foreground">{m.label}</p>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className={`text-3xl md:text-4xl font-display font-bold ${m.color} tabular-nums`}>{m.value}</span>
                <span className="text-xs text-muted-foreground">{m.unit}</span>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
