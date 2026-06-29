"use client";
import { useMutation, useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Copy, Download, Hammer, Loader2, Plus, Save, Sparkles, Trash2, Wand2 } from "lucide-react";
import * as React from "react";
import { toast } from "sonner";
import { ChartCard } from "@/components/charts/chart-card";
import { EnergyIcon } from "@/components/shared/energy-icon";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { endpoints } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";
import { searchCards } from "@/services/cards";
import type { CardSummary } from "@/types/api";
import { BarChart } from "@/components/charts/bar-chart";

interface DeckSlot { card: CardSummary; count: number }

export default function DeckBuilderPage() {
  const [query, setQuery] = React.useState("");
  const [deck, setDeck] = React.useState<DeckSlot[]>([]);
  const [archetype, setArchetype] = React.useState("");
  const [seed, setSeed] = React.useState("");

  const cards = useQuery({
    queryKey: ["cards", query],
    queryFn: () => searchCards(query, {}),
  });

  const total = deck.reduce((s, d) => s + d.count, 0);

  const generate = useMutation({
    mutationFn: () =>
      endpoints.deckBuild({
        seed_cards: seed ? [seed] : null,
        archetype: archetype || null,
        n_candidates: 1,
      }),
    onSuccess: (data) => {
      toast.success("Deck generated", { description: `Score ${data.score.toFixed(1)}` });
    },
    onError: () => toast.error("Backend unavailable — connect to FastAPI to generate decks"),
  });

  const addCard = (c: CardSummary) => {
    setDeck((d) => {
      const existing = d.find((x) => x.card.card_id === c.card_id);
      if (existing) {
        if (existing.count >= 4 && c.category !== "Energy") return d;
        return d.map((x) => (x.card.card_id === c.card_id ? { ...x, count: x.count + 1 } : x));
      }
      return [...d, { card: c, count: 1 }];
    });
  };
  const removeCard = (id: number) => setDeck((d) => d.filter((x) => x.card.card_id !== id));
  const decrement = (id: number) =>
    setDeck((d) => d.flatMap((x) => (x.card.card_id === id ? (x.count > 1 ? [{ ...x, count: x.count - 1 }] : []) : [x])));

  const counts = {
    pokemon: deck.filter((s) => s.card.category === "Pokémon").reduce((a, b) => a + b.count, 0),
    trainer: deck.filter((s) => s.card.category === "Trainer").reduce((a, b) => a + b.count, 0),
    energy: deck.filter((s) => s.card.category === "Energy").reduce((a, b) => a + b.count, 0),
  };
  const energyCurve = computeEnergyCurve(deck);

  const ptcgLive = generate.data?.ptcg_live ?? exportToPtcgLive(deck);

  return (
    <div className="container max-w-7xl py-6 md:py-10 space-y-6">
      <PageHeader
        title="Deck Builder"
        description="Drag and click to build a 60-card deck. The AI scores synergy as you go."
        icon={<Hammer className="size-5" />}
        actions={
          <div className="flex gap-2">
            <Input placeholder="Seed card" value={seed} onChange={(e) => setSeed(e.target.value)} className="w-40 h-9" />
            <Input placeholder="Archetype" value={archetype} onChange={(e) => setArchetype(e.target.value)} className="w-32 h-9" />
            <Button variant="gradient" loading={generate.isPending} onClick={() => generate.mutate()} size="sm">
              <Wand2 className="size-4" /> Generate
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_460px] gap-4">
        {/* Card library */}
        <div className="space-y-4">
          <div className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Input
                placeholder="Search 1,267 cards — by name…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="flex-1"
              />
              <Badge variant="info">{cards.data?.length ?? 0} results</Badge>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-[60vh] overflow-y-auto pr-1">
              {cards.data?.map((c, i) => (
                <motion.button
                  key={c.card_id}
                  onClick={() => addCard(c)}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.015 }}
                  whileHover={{ y: -2 }}
                  className="group relative overflow-hidden text-left rounded-xl border border-border/40 bg-background/30 p-3 hover:border-electric/40 hover:bg-electric/5 transition"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5 mb-0.5">
                        <p className="font-semibold text-sm truncate">{c.name}</p>
                        {c.rule_box && <Badge variant="warning" className="text-[9px] h-4 px-1">ex</Badge>}
                      </div>
                      <p className="text-[10px] text-muted-foreground">
                        {c.category} {c.stage && `· ${c.stage}`} {c.expansion && `· ${c.expansion}`}
                      </p>
                    </div>
                    {c.hp && (
                      <span className="font-mono font-bold text-xs tabular-nums shrink-0">{c.hp}</span>
                    )}
                  </div>
                  {c.attacks && c.attacks.length > 0 && (
                    <div className="mt-2 flex items-center gap-1 text-[10px] text-muted-foreground">
                      {c.attacks[0].cost.slice(0, 4).map((e, i) => (
                        <EnergyIcon key={i} type={e} size="sm" />
                      ))}
                      <span className="ml-1 truncate">{c.attacks[0].name}</span>
                      <span className="ml-auto font-mono">{c.attacks[0].damage}</span>
                    </div>
                  )}
                  <div className="absolute right-2 bottom-2 opacity-0 group-hover:opacity-100 transition">
                    <Plus className="size-4 text-electric" />
                  </div>
                </motion.button>
              ))}
            </div>
          </div>

          <ChartCard title="Energy curve" description="Sum of energy costs by Pokémon" height="h-56">
            <BarChart data={energyCurve} xKey="cost" yKey="count" color="#5E5CFF" />
          </ChartCard>
        </div>

        {/* Decklist */}
        <div className="space-y-4">
          <div className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl overflow-hidden flex flex-col h-[calc(100vh-200px)]">
            <div className="p-5 border-b border-border/40">
              <div className="flex items-center justify-between mb-3">
                <p className="font-semibold text-sm">Decklist</p>
                <span className={cn("font-mono font-bold tabular-nums", total === 60 ? "text-emerald-400" : "text-muted-foreground")}>
                  {total}/60
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <DeckStat label="Pokémon" value={counts.pokemon} />
                <DeckStat label="Trainers" value={counts.trainer} />
                <DeckStat label="Energy" value={counts.energy} />
              </div>
            </div>
            <ScrollArea className="flex-1 p-3">
              {deck.length === 0 ? (
                <EmptyDeck />
              ) : (
                <ul className="space-y-1.5">
                  {deck.map((slot) => (
                    <li key={slot.card.card_id} className="flex items-center gap-2 rounded-lg border border-border/30 bg-background/30 p-2">
                      <span className="font-mono font-bold text-sm w-5 text-center text-electric">{slot.count}</span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate">{slot.card.name}</p>
                        <p className="text-[10px] text-muted-foreground truncate">{slot.card.expansion} {slot.card.collection_number}</p>
                      </div>
                      <button onClick={() => decrement(slot.card.card_id)} className="size-7 rounded-md grid place-items-center hover:bg-muted/60" aria-label="Remove one">
                        −
                      </button>
                      <button onClick={() => removeCard(slot.card.card_id)} className="size-7 rounded-md grid place-items-center hover:bg-rose-500/20 text-rose-400" aria-label="Remove all">
                        <Trash2 className="size-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </ScrollArea>
            <div className="border-t border-border/40 p-3 grid grid-cols-3 gap-1.5">
              <Button variant="glass" size="sm" onClick={() => navigator.clipboard.writeText(ptcgLive).then(() => toast.success("Copied PTCG Live export"))}>
                <Copy className="size-3.5" /> Copy
              </Button>
              <Button variant="glass" size="sm" onClick={() => toast.success("Saved (mock)")}>
                <Save className="size-3.5" /> Save
              </Button>
              <Button variant="glass" size="sm" onClick={() => toast.success("Exported (mock)")}>
                <Download className="size-3.5" /> Export
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyDeck() {
  return (
    <div className="text-center py-12 px-4">
      <div className="size-12 rounded-2xl bg-brand-gradient grid place-items-center mx-auto mb-3 [background-size:200%_100%] animate-gradient-flow">
        <Sparkles className="size-5 text-white" />
      </div>
      <p className="font-semibold text-sm">Build a deck</p>
      <p className="text-xs text-muted-foreground mt-1 max-w-xs mx-auto">
        Search and click cards on the left to add them, or use Generate to let the AI build one.
      </p>
    </div>
  );
}

function DeckStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border/30 bg-background/30 py-2">
      <p className="text-[9px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="font-mono font-bold text-base tabular-nums">{value}</p>
    </div>
  );
}

function computeEnergyCurve(deck: DeckSlot[]) {
  const curve: Record<number, number> = {};
  for (const slot of deck) {
    if (slot.card.category !== "Pokémon" || !slot.card.attacks?.length) continue;
    const cost = slot.card.attacks[0].cost.length;
    curve[cost] = (curve[cost] ?? 0) + slot.count;
  }
  return Array.from({ length: 5 }, (_, i) => ({ cost: i + 1, count: curve[i + 1] ?? 0 }));
}

function exportToPtcgLive(deck: DeckSlot[]): string {
  const lines: string[] = [];
  lines.push(`Pokémon: ${deck.filter((s) => s.card.category === "Pokémon").reduce((a, b) => a + b.count, 0)}`);
  for (const s of deck.filter((s) => s.card.category === "Pokémon")) lines.push(`${s.count} ${s.card.name} ${s.card.expansion} ${s.card.collection_number}`);
  lines.push("");
  lines.push(`Trainer: ${deck.filter((s) => s.card.category === "Trainer").reduce((a, b) => a + b.count, 0)}`);
  for (const s of deck.filter((s) => s.card.category === "Trainer")) lines.push(`${s.count} ${s.card.name} ${s.card.expansion} ${s.card.collection_number}`);
  lines.push("");
  lines.push(`Energy: ${deck.filter((s) => s.card.category === "Energy").reduce((a, b) => a + b.count, 0)}`);
  for (const s of deck.filter((s) => s.card.category === "Energy")) lines.push(`${s.count} ${s.card.name} ${s.card.expansion} ${s.card.collection_number}`);
  return lines.join("\n");
}
