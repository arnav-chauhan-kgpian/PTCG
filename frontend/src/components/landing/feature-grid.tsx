"use client";
import { motion } from "framer-motion";
import {
  Brain,
  Cpu,
  Database,
  GitBranch,
  Layers,
  Network,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from "lucide-react";

const features = [
  {
    icon: Brain,
    title: "Neural MCTS",
    description: "PUCT search with shared inference cache. 359 iter/s on real card states.",
    accent: "from-electric/30 to-electric/0",
    iconColor: "text-electric",
  },
  {
    icon: Layers,
    title: "Immutable Game State",
    description: "Frozen Pydantic models, 741-dim feature encoder, SHA-256 hashing.",
    accent: "from-indigo/30 to-indigo/0",
    iconColor: "text-indigo-light",
  },
  {
    icon: Cpu,
    title: "Rules Engine",
    description: "Simulator correctness 1.0000. Tools, stadiums, special energy, status conditions.",
    accent: "from-purple/30 to-purple/0",
    iconColor: "text-purple-light",
  },
  {
    icon: TrendingUp,
    title: "Training Pipeline",
    description: "Self-play → train → arena → promotion → checkpoint. AlphaZero loop end-to-end.",
    accent: "from-gold/30 to-gold/0",
    iconColor: "text-gold-light",
  },
  {
    icon: Database,
    title: "Knowledge Graph",
    description: "1,267 cards · evolution chains · effect parser · 218 abilities indexed.",
    accent: "from-electric/30 to-electric/0",
    iconColor: "text-electric",
  },
  {
    icon: Network,
    title: "Deck Intelligence",
    description: "Archetype detection, consistency scoring, synergy graphs, win-condition analysis.",
    accent: "from-purple/30 to-purple/0",
    iconColor: "text-purple-light",
  },
  {
    icon: Sparkles,
    title: "Deck Builder",
    description: "Constructive generator + repair engine. Beam, hill-climb, annealing strategies.",
    accent: "from-indigo/30 to-indigo/0",
    iconColor: "text-indigo-light",
  },
  {
    icon: ShieldCheck,
    title: "Production Ready",
    description: "Docker, REST API, CLI, CI/CD. 1,065 passing tests, 90% coverage, ruff-clean.",
    accent: "from-emerald-500/30 to-emerald-500/0",
    iconColor: "text-emerald-400",
  },
  {
    icon: GitBranch,
    title: "Explainable AI",
    description: "Top moves · visit counts · principal variation · expected prize swing.",
    accent: "from-gold/30 to-gold/0",
    iconColor: "text-gold-light",
  },
];

export function FeatureGrid() {
  return (
    <section id="features" className="relative py-24 md:py-32 container">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.5 }}
        className="text-center mb-16"
      >
        <span className="inline-flex items-center gap-1.5 rounded-full glass px-3 py-1 text-xs font-medium uppercase tracking-wider mb-4">
          <span className="size-1.5 rounded-full bg-purple animate-pulse" />
          Capabilities
        </span>
        <h2 className="font-display font-bold text-3xl md:text-5xl tracking-tight">
          Every layer of the stack,{" "}
          <span className="text-gradient">production-grade</span>
        </h2>
        <p className="mt-4 text-base md:text-lg text-muted-foreground max-w-2xl mx-auto">
          From parser to policy network — 14 packages, 174 modules, all wired together with
          measurable correctness and performance.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-5">
        {features.map((f, i) => (
          <motion.div
            key={f.title}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-50px" }}
            transition={{ duration: 0.4, delay: i * 0.04 }}
            whileHover={{ y: -4 }}
            className="group relative overflow-hidden rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-6 hover:border-border transition-colors"
          >
            <div className={`absolute -top-16 -right-16 size-48 rounded-full bg-gradient-radial opacity-0 group-hover:opacity-70 blur-3xl transition-opacity duration-500 ${f.accent}`} />
            <div className="relative">
              <div className={`flex items-center justify-center size-12 rounded-xl border border-border/60 bg-background/60 ${f.iconColor} mb-4 group-hover:scale-110 transition-transform`}>
                <f.icon className="size-5" />
              </div>
              <h3 className="font-display font-semibold text-lg mb-1.5">{f.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{f.description}</p>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
