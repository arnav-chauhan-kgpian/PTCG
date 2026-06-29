import type { CardSummary } from "@/types/api";

/** Sample card database — swap to backend `/cards` when wired up. */
const SAMPLE: CardSummary[] = [
  {
    card_id: 125,
    name: "Charizard ex",
    category: "Pokémon",
    pokemon_type: "Fire",
    stage: "Stage 2",
    hp: 330,
    rule_box: "Pokémon ex",
    expansion: "OBF",
    collection_number: "125",
    ability_name: "Infernal Reign",
    weakness: "Water",
    retreat_cost: 2,
    attacks: [
      { name: "Burning Darkness", cost: ["{R}", "{R}"], damage: 180, effect: "+30 damage for each Prize card your opponent has taken." },
    ],
  },
  {
    card_id: 164,
    name: "Pidgeot ex",
    category: "Pokémon",
    pokemon_type: "Colorless",
    stage: "Stage 2",
    hp: 280,
    rule_box: "Pokémon ex",
    expansion: "OBF",
    collection_number: "164",
    ability_name: "Quick Search",
    weakness: "Lightning",
    retreat_cost: 0,
    attacks: [
      { name: "Blustery Wind", cost: ["{C}", "{C}", "{C}"], damage: 130 },
    ],
  },
  {
    card_id: 47,
    name: "Iron Hands ex",
    category: "Pokémon",
    pokemon_type: "Lightning",
    stage: "Basic",
    hp: 230,
    rule_box: "Pokémon ex",
    expansion: "PAR",
    collection_number: "70",
    ability_name: "Amp You Very Much",
    weakness: "Fighting",
    retreat_cost: 4,
    attacks: [
      { name: "Arm Press", cost: ["{L}", "{F}", "{C}"], damage: 160 },
    ],
  },
  {
    card_id: 245,
    name: "Iono",
    category: "Trainer",
    expansion: "PAL",
    collection_number: "185",
    effect: "Each player shuffles their hand into their deck and draws cards equal to their remaining Prize cards.",
  },
  {
    card_id: 197,
    name: "Boss's Orders",
    category: "Trainer",
    expansion: "PAL",
    collection_number: "172",
    effect: "Switch in 1 of your opponent's Benched Pokémon to the Active Spot.",
  },
  {
    card_id: 309,
    name: "Ultra Ball",
    category: "Trainer",
    expansion: "SVI",
    collection_number: "196",
    effect: "Discard 2 cards from your hand. Search your deck for a Pokémon, reveal it, and put it into your hand.",
  },
  {
    card_id: 422,
    name: "Buddy-Buddy Poffin",
    category: "Trainer",
    expansion: "TWM",
    collection_number: "144",
    effect: "Search your deck for up to 2 Basic Pokémon with 70 HP or less, reveal them, and put them into your hand.",
  },
  {
    card_id: 99,
    name: "Pidgeot ex (Quick Search)",
    category: "Pokémon",
    pokemon_type: "Colorless",
    stage: "Stage 2",
    hp: 280,
    rule_box: "Pokémon ex",
    expansion: "OBF",
    collection_number: "164",
    ability_name: "Quick Search",
    weakness: "Lightning",
    retreat_cost: 0,
    attacks: [{ name: "Blustery Wind", cost: ["{C}", "{C}", "{C}"], damage: 130 }],
  },
  {
    card_id: 11,
    name: "Squawkabilly ex",
    category: "Pokémon",
    pokemon_type: "Colorless",
    stage: "Basic",
    hp: 160,
    rule_box: "Pokémon ex",
    expansion: "PAF",
    collection_number: "169",
    ability_name: "Hustle Drum",
    weakness: "Lightning",
    retreat_cost: 1,
    attacks: [{ name: "Slap", cost: ["{C}"], damage: 30 }],
  },
  {
    card_id: 313,
    name: "Gardevoir ex",
    category: "Pokémon",
    pokemon_type: "Psychic",
    stage: "Stage 2",
    hp: 310,
    rule_box: "Pokémon ex",
    expansion: "SVI",
    collection_number: "245",
    ability_name: "Psychic Embrace",
    weakness: "Metal",
    retreat_cost: 2,
    attacks: [{ name: "Miracle Force", cost: ["{P}", "{P}", "{C}"], damage: 190 }],
  },
  {
    card_id: 188,
    name: "Lugia ex",
    category: "Pokémon",
    pokemon_type: "Colorless",
    stage: "Basic",
    hp: 280,
    rule_box: "Pokémon ex",
    expansion: "SIT",
    collection_number: "139",
    ability_name: "Summoning Star",
    weakness: "Lightning",
    retreat_cost: 3,
    attacks: [{ name: "Storm Dive", cost: ["{C}", "{C}", "{C}", "{C}"], damage: 220 }],
  },
  {
    card_id: 401,
    name: "Lightning Energy",
    category: "Energy",
    expansion: "SVE",
    collection_number: "4",
    effect: "Provides 1 {L} Energy.",
  },
  {
    card_id: 402,
    name: "Double Turbo Energy",
    category: "Energy",
    expansion: "BRS",
    collection_number: "151",
    effect: "Provides 2 colorless Energy. Attacks of the Pokémon this card is attached to do 20 less damage to opponent's Active.",
  },
];

export async function searchCards(query: string, filters: CardFilters): Promise<CardSummary[]> {
  await new Promise((r) => setTimeout(r, 80));
  const q = query.toLowerCase().trim();
  return SAMPLE.filter((c) => {
    if (q && !c.name.toLowerCase().includes(q)) return false;
    if (filters.category && c.category !== filters.category) return false;
    if (filters.type && c.pokemon_type !== filters.type) return false;
    if (filters.stage && c.stage !== filters.stage) return false;
    if (filters.ruleBox && c.rule_box !== filters.ruleBox) return false;
    if (filters.minHp != null && (c.hp ?? 0) < filters.minHp) return false;
    return true;
  });
}

export async function getCard(id: number): Promise<CardSummary | null> {
  return SAMPLE.find((c) => c.card_id === id) ?? null;
}

export interface CardFilters {
  category?: CardSummary["category"];
  type?: string;
  stage?: string;
  ruleBox?: string;
  minHp?: number;
}
