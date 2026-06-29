"use client";
import { motion } from "framer-motion";
import { ArrowRight, BookOpen, Code2, Github, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { siteConfig } from "@/config/site";

export default function AboutPage() {
  return (
    <div className="container max-w-4xl py-6 md:py-10 space-y-6">
      <PageHeader title="About" description="Open-source, MIT-licensed Pokémon TCG AI framework." icon={<Sparkles className="size-5" />} />

      <motion.div
        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-8 space-y-4 relative overflow-hidden"
      >
        <div className="absolute -top-20 -right-20 size-60 rounded-full bg-electric/20 blur-3xl" />
        <div className="absolute -bottom-20 -left-20 size-60 rounded-full bg-purple/20 blur-3xl" />
        <div className="relative space-y-4">
          <Badge variant="gradient">v1.0 — Production release</Badge>
          <h2 className="font-display font-bold text-2xl md:text-3xl tracking-tight">
            An AlphaZero-class <span className="text-gradient">Pokémon TCG AI</span>
          </h2>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Built across 11 implementation phases — from a card knowledge layer through deck intelligence,
            simulator, MCTS with neural inference, AlphaZero training, and a competition-ready agent with a
            REST API and CLI.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="gradient">
              <a href={siteConfig.links.github} target="_blank" rel="noreferrer">
                <Github className="size-4" /> Star on GitHub
                <ArrowRight className="size-4" />
              </a>
            </Button>
            <Button variant="glass">
              <BookOpen className="size-4" /> Read the docs
            </Button>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Tests passing", value: "1,065" },
          { label: "Coverage", value: "90%" },
          { label: "Simulator correctness", value: "1.0000" },
          { label: "Production modules", value: "174" },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border border-border/40 bg-card/40 backdrop-blur p-4 text-center">
            <p className="text-2xl font-display font-bold text-gradient tabular-nums">{s.value}</p>
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-6">
        <p className="font-semibold text-sm mb-3 flex items-center gap-2"><Code2 className="size-4" /> Built with</p>
        <div className="flex flex-wrap gap-2 text-xs">
          {["Python 3.12", "Pydantic", "PyTorch", "FastAPI", "Next.js 15", "React 19", "Tailwind", "Framer Motion", "shadcn/ui", "TanStack Query", "Zustand", "Recharts"].map((s) => (
            <span key={s} className="rounded-full border border-border/60 bg-background/30 px-3 py-1">{s}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
