"use client";
import { useMutation } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Brain, FileText, Upload, Wand2 } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { endpoints } from "@/lib/api/endpoints";

const sample = `Pokémon: 12
4 Charizard ex OBF 125
2 Charmeleon OBF 26
4 Charmander PAF 7
2 Pidgeot ex OBF 164

Trainer: 32
4 Iono PAL 185
3 Boss's Orders PAL 172
4 Ultra Ball SVI 196
4 Rare Candy SVI 191
4 Nest Ball PAF 84
3 Switch SVI 194
2 Earthen Vessel PAR 163
4 Buddy-Buddy Poffin TWM 144

Energy: 16
16 Fire Energy SVE 2`;

export default function DeckAnalyzerPage() {
  const [text, setText] = React.useState(sample);

  const analyze = useMutation({
    mutationFn: () => endpoints.deckAnalyze({ decklist: text }),
    onError: () => toast.error("Backend unavailable — showing mock results"),
  });

  // Provide mock fallback when backend is offline
  const result = analyze.data ?? (analyze.isError ? {
    archetype: "Charizard ex / Pidgeot ex",
    consistency_grade: "A",
    synergy_score: 0.78,
  } : null);

  return (
    <div className="container max-w-7xl py-6 md:py-10 space-y-6">
      <PageHeader
        title="Deck Analyzer"
        description="Paste a decklist (PTCG Live format). The AI scores consistency, archetype, and synergy."
        icon={<Brain className="size-5" />}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-5 space-y-3">
            <div className="flex items-center justify-between">
              <p className="font-semibold text-sm">Decklist input</p>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm"><Upload className="size-3.5" /> Upload</Button>
                <Button variant="ghost" size="sm" onClick={() => setText(sample)}><FileText className="size-3.5" /> Sample</Button>
              </div>
            </div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="w-full h-96 rounded-lg border border-input bg-background/40 backdrop-blur px-3 py-2 font-mono text-xs leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring resize-none"
              spellCheck={false}
            />
            <div className="flex justify-between items-center text-xs text-muted-foreground">
              <span>{text.split("\n").length} lines</span>
              <Button variant="gradient" loading={analyze.isPending} onClick={() => analyze.mutate()}>
                <Wand2 className="size-4" /> Analyze deck
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5 space-y-4">
            <p className="font-semibold text-sm">Analysis</p>
            {!result ? (
              <EmptyState />
            ) : (
              <Results result={result} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="text-center py-12">
      <div className="size-12 rounded-2xl bg-brand-gradient grid place-items-center mx-auto mb-3 [background-size:200%_100%] animate-gradient-flow">
        <Brain className="size-5 text-white" />
      </div>
      <p className="font-semibold text-sm">Ready to analyze</p>
      <p className="text-xs text-muted-foreground mt-1">Paste a deck list and hit Analyze.</p>
    </div>
  );
}

function Results({ result }: { result: { archetype: string; consistency_grade: string; synergy_score: number } }) {
  const synergyPct = Math.round(result.synergy_score * 100);
  const strengths = [
    "High consistency Rare Candy + Pidgeot ex tutor engine",
    "Reliable single-turn KO via Burning Darkness power scaling",
    "Strong gust + KO threat with Boss's Orders",
  ];
  const weaknesses = [
    "Weak to Path to the Peak (locks Charizard's setup)",
    "Limited recovery vs Iono disruption late",
  ];
  const recommendations = [
    "Consider +1 Counter Catcher",
    "Run 2 Energy Switch instead of 4 Switch",
    "Add 1 Forest Seal Stone for late-game burst",
  ];

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
      <div className="grid grid-cols-3 gap-2">
        <Scorecard label="Archetype" value={result.archetype} accent="electric" big />
        <Scorecard label="Consistency" value={result.consistency_grade} accent="emerald" />
        <Scorecard label="Synergy" value={`${synergyPct}/100`} accent="purple" />
      </div>

      <div>
        <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">Synergy score</p>
        <Progress value={synergyPct} />
      </div>

      <Section title="Strengths" items={strengths} variant="success" />
      <Section title="Weaknesses" items={weaknesses} variant="warning" />
      <Section title="Recommendations" items={recommendations} variant="info" />
    </motion.div>
  );
}

function Scorecard({ label, value, accent, big }: { label: string; value: string; accent: "electric" | "emerald" | "purple"; big?: boolean }) {
  const colors = {
    electric: "border-electric/30 bg-electric/5 text-electric",
    emerald: "border-emerald-500/30 bg-emerald-500/5 text-emerald-400",
    purple: "border-purple/30 bg-purple/5 text-purple-light",
  };
  return (
    <div className={`rounded-xl border p-3 ${colors[accent]}`}>
      <p className="text-[10px] uppercase tracking-wider opacity-80">{label}</p>
      <p className={`font-bold mt-1 ${big ? "text-sm leading-snug" : "text-2xl"} truncate`}>{value}</p>
    </div>
  );
}

function Section({ title, items, variant }: { title: string; items: string[]; variant: "success" | "warning" | "info" }) {
  return (
    <div>
      <Badge variant={variant} className="mb-2">{title}</Badge>
      <ul className="space-y-1.5">
        {items.map((it, i) => (
          <li key={i} className="text-xs text-foreground/85 leading-relaxed flex items-start gap-2">
            <span className="mt-1.5 size-1 rounded-full bg-muted-foreground shrink-0" />
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}
