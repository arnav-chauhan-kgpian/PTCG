"use client";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Library, Search, Sliders } from "lucide-react";
import * as React from "react";
import { EnergyIcon } from "@/components/shared/energy-icon";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { searchCards } from "@/services/cards";
import type { CardSummary } from "@/types/api";

const types = ["Fire", "Water", "Grass", "Lightning", "Psychic", "Fighting", "Dark", "Metal", "Colorless"];
const stages = ["Basic", "Stage 1", "Stage 2"];
const categories: CardSummary["category"][] = ["Pokémon", "Trainer", "Energy"];

export default function CardsPage() {
  const [query, setQuery] = React.useState("");
  const [filters, setFilters] = React.useState<{ category?: CardSummary["category"]; type?: string; stage?: string }>({});
  const [selected, setSelected] = React.useState<CardSummary | null>(null);

  const cards = useQuery({
    queryKey: ["cards", query, filters],
    queryFn: () => searchCards(query, filters),
  });

  return (
    <div className="container max-w-7xl py-6 md:py-10 space-y-6">
      <PageHeader
        title="Card Database"
        description="1,267 Standard-format cards · parsed effects · indexed relationships"
        icon={<Library className="size-5" />}
        actions={<Badge variant="info">{cards.data?.length ?? 0} results</Badge>}
      />

      <div className="rounded-2xl border border-border/40 bg-card/40 backdrop-blur-xl p-4 space-y-3">
        <div className="relative">
          <Search className="size-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search cards by name…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="pl-10 h-11 text-sm"
          />
        </div>

        <div className="flex flex-wrap gap-2">
          <FilterGroup label="Category">
            {categories.map((c) => (
              <Chip key={c} active={filters.category === c} onClick={() => setFilters((f) => ({ ...f, category: f.category === c ? undefined : c }))}>{c}</Chip>
            ))}
          </FilterGroup>
          <FilterGroup label="Stage">
            {stages.map((s) => (
              <Chip key={s} active={filters.stage === s} onClick={() => setFilters((f) => ({ ...f, stage: f.stage === s ? undefined : s }))}>{s}</Chip>
            ))}
          </FilterGroup>
          <FilterGroup label="Type">
            {types.map((t) => (
              <Chip key={t} active={filters.type === t} onClick={() => setFilters((f) => ({ ...f, type: f.type === t ? undefined : t }))}>{t}</Chip>
            ))}
          </FilterGroup>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
        {cards.data?.map((c, i) => (
          <motion.button
            key={c.card_id}
            onClick={() => setSelected(c)}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.02 }}
            whileHover={{ y: -4 }}
            className="group relative overflow-hidden rounded-xl border border-border/40 bg-card/40 backdrop-blur p-4 text-left hover:border-electric/40 transition-colors"
          >
            <div className="absolute -top-12 -right-12 size-32 rounded-full bg-electric/10 blur-3xl group-hover:bg-electric/20 transition" />
            <div className="relative">
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-sm truncate">{c.name}</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {c.category} {c.expansion && `· ${c.expansion} ${c.collection_number}`}
                  </p>
                </div>
                {c.hp && <span className="font-mono font-bold text-xs tabular-nums text-rose-400">HP {c.hp}</span>}
              </div>
              {c.attacks?.[0] && (
                <div className="flex items-center gap-1 mt-2">
                  {c.attacks[0].cost.slice(0, 4).map((e, i) => (
                    <EnergyIcon key={i} type={e} size="sm" />
                  ))}
                  <span className="text-[10px] ml-auto font-mono font-bold">{c.attacks[0].damage}</span>
                </div>
              )}
              {c.ability_name && (
                <Badge variant="warning" className="mt-2 text-[9px]">⚡ {c.ability_name}</Badge>
              )}
              {c.rule_box && (
                <Badge variant="gradient" className="mt-1 text-[9px] ml-1">ex</Badge>
              )}
              {c.category === "Trainer" && c.effect && (
                <p className="text-[10px] text-muted-foreground line-clamp-2 mt-2 leading-snug">{c.effect}</p>
              )}
            </div>
          </motion.button>
        ))}
      </div>

      <Dialog open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <DialogContent className="max-w-md">
          {selected && <CardDetail card={selected} />}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function FilterGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1 flex-wrap">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground mr-1">{label}</span>
      {children}
    </div>
  );
}

function Chip({ active, children, onClick }: { active?: boolean; children: React.ReactNode; onClick?: () => void }) {
  return (
    <button onClick={onClick} className={`px-2.5 py-1 text-[11px] rounded-full border transition ${active ? "border-electric bg-electric/10 text-electric" : "border-border/60 hover:border-border bg-background/30"}`}>
      {children}
    </button>
  );
}

function CardDetail({ card }: { card: CardSummary }) {
  return (
    <div>
      <DialogHeader className="mb-3">
        <DialogTitle>{card.name}</DialogTitle>
        <p className="text-xs text-muted-foreground">
          {card.category} {card.stage && `· ${card.stage}`} {card.expansion && `· ${card.expansion} ${card.collection_number}`}
        </p>
      </DialogHeader>
      <div className="space-y-3">
        {card.hp && (
          <div className="flex items-center gap-3">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">HP</span>
            <span className="font-mono font-bold text-base">{card.hp}</span>
            {card.pokemon_type && <Badge variant="outline" className="ml-auto">{card.pokemon_type}</Badge>}
          </div>
        )}
        {card.ability_name && (
          <div className="rounded-xl border border-gold/30 bg-gold/5 p-3">
            <Badge variant="warning" className="mb-1">Ability</Badge>
            <p className="text-sm font-semibold">{card.ability_name}</p>
          </div>
        )}
        {card.attacks?.map((a, i) => (
          <div key={i} className="rounded-xl border border-border/60 bg-background/30 p-3">
            <div className="flex items-center gap-2 mb-1">
              {a.cost.map((e, j) => <EnergyIcon key={j} type={e} size="md" />)}
              <p className="font-semibold text-sm">{a.name}</p>
              <span className="font-mono font-bold ml-auto">{a.damage}</span>
            </div>
            {a.effect && <p className="text-xs text-muted-foreground leading-relaxed mt-1">{a.effect}</p>}
          </div>
        ))}
        {card.effect && card.category !== "Pokémon" && (
          <p className="text-xs leading-relaxed text-foreground/80">{card.effect}</p>
        )}
        <div className="flex flex-wrap gap-3 text-xs">
          {card.weakness && <span><span className="text-muted-foreground">Weak:</span> {card.weakness}</span>}
          {card.resistance && <span><span className="text-muted-foreground">Resist:</span> {card.resistance}</span>}
          {card.retreat_cost != null && <span><span className="text-muted-foreground">Retreat:</span> {card.retreat_cost}</span>}
        </div>
      </div>
    </div>
  );
}
