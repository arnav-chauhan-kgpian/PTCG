/** Mock battle state for the live-battle showcase page. */
export interface BattleCard {
  id: string;
  name: string;
  hp_max: number;
  hp_current: number;
  type: string;
  attached_energy: string[];
  conditions: string[];
  stage: "Basic" | "Stage 1" | "Stage 2";
}

export interface BattleSide {
  player: "you" | "opponent";
  username: string;
  active: BattleCard | null;
  bench: BattleCard[];
  hand_count: number;
  deck_count: number;
  discard_count: number;
  lost_zone_count: number;
  prize_count: number;
  conditions: string[];
}

export interface BattleState {
  turn: number;
  current_player: "you" | "opponent";
  you: BattleSide;
  opponent: BattleSide;
  log: BattleLog[];
  recommended: BattleAction[];
  search_stats: {
    iterations: number;
    nodes_created: number;
    cache_hit_rate: number;
    iterations_per_sec: number;
    avg_branching: number;
    pv_depth: number;
  };
}

export interface BattleLog {
  id: string;
  turn: number;
  player: "you" | "opponent";
  text: string;
  kind: "attack" | "trainer" | "ability" | "energy" | "evolve" | "system";
  timestamp: string;
}

export interface BattleAction {
  id: string;
  label: string;
  description: string;
  visits: number;
  visit_share: number;
  q_value: number;
  prior: number;
  policy: number;
  win_probability: number;
  principal_variation: string[];
  expected_prize_swing: number;
}

const energyEmoji: Record<string, string> = {
  R: "🔥", W: "💧", G: "🌿", L: "⚡", P: "🔮", F: "🥊", D: "🌑", M: "⚙️", C: "⚪",
};

export function getEnergyToken(symbol: string): string {
  const key = symbol.replace(/[{}]/g, "");
  return energyEmoji[key] ?? "⚪";
}

export async function getDemoBattleState(): Promise<BattleState> {
  const yourActive: BattleCard = {
    id: "your-active", name: "Charizard ex", type: "Fire", hp_max: 330,
    hp_current: 230, attached_energy: ["R", "R", "R"], conditions: [], stage: "Stage 2",
  };
  const yourBench: BattleCard[] = [
    { id: "y2", name: "Pidgeot ex", type: "Colorless", hp_max: 280, hp_current: 280, attached_energy: ["C"], conditions: [], stage: "Stage 2" },
    { id: "y3", name: "Charmander", type: "Fire", hp_max: 70, hp_current: 70, attached_energy: [], conditions: [], stage: "Basic" },
    { id: "y4", name: "Rotom V", type: "Lightning", hp_max: 190, hp_current: 190, attached_energy: ["L"], conditions: [], stage: "Basic" },
  ];
  const oppActive: BattleCard = {
    id: "opp-active", name: "Gardevoir ex", type: "Psychic", hp_max: 310,
    hp_current: 180, attached_energy: ["P", "P", "C"], conditions: ["Burned"], stage: "Stage 2",
  };
  const oppBench: BattleCard[] = [
    { id: "o2", name: "Kirlia", type: "Psychic", hp_max: 80, hp_current: 80, attached_energy: [], conditions: [], stage: "Stage 1" },
    { id: "o3", name: "Ralts", type: "Psychic", hp_max: 60, hp_current: 60, attached_energy: [], conditions: [], stage: "Basic" },
  ];

  return {
    turn: 7,
    current_player: "you",
    you: {
      player: "you", username: "Pokémon AI",
      active: yourActive, bench: yourBench,
      hand_count: 6, deck_count: 41, discard_count: 7, lost_zone_count: 0,
      prize_count: 3, conditions: [],
    },
    opponent: {
      player: "opponent", username: "Opponent",
      active: oppActive, bench: oppBench,
      hand_count: 5, deck_count: 38, discard_count: 11, lost_zone_count: 0,
      prize_count: 4, conditions: [],
    },
    log: [
      { id: "1", turn: 6, player: "opponent", kind: "evolve", text: "Opponent evolved Kirlia into Gardevoir ex.", timestamp: minutesAgo(2) },
      { id: "2", turn: 6, player: "opponent", kind: "ability", text: "Used Psychic Embrace — attached Psychic Energy from discard.", timestamp: minutesAgo(2) },
      { id: "3", turn: 6, player: "opponent", kind: "attack", text: "Miracle Force for 190 damage.", timestamp: minutesAgo(1) },
      { id: "4", turn: 7, player: "you", kind: "system", text: "Your turn — drew a card.", timestamp: minutesAgo(0.4) },
      { id: "5", turn: 7, player: "you", kind: "trainer", text: "Played Iono — both players shuffle hand, draw 3.", timestamp: minutesAgo(0.2) },
    ],
    recommended: [
      {
        id: "a1", label: "Attack — Burning Darkness",
        description: "Charizard ex hits for 180 base + 30 per opponent prize taken (×4 = +120). Predicted KO.",
        visits: 487, visit_share: 0.61, q_value: 0.74, prior: 0.42, policy: 0.55,
        win_probability: 0.74,
        principal_variation: ["Attack — Burning Darkness", "Opponent promotes Kirlia", "Boss's Orders → Ralts", "Charizard attacks Ralts"],
        expected_prize_swing: 2.0,
      },
      {
        id: "a2", label: "Play — Iono",
        description: "Disrupt opponent's hand. Hold attack until next turn.",
        visits: 198, visit_share: 0.25, q_value: 0.61, prior: 0.18, policy: 0.27,
        win_probability: 0.61,
        principal_variation: ["Play — Iono", "Opponent draws 4", "Opponent attaches energy", "Your turn 8 — attack"],
        expected_prize_swing: 0.5,
      },
      {
        id: "a3", label: "Use ability — Quick Search (Pidgeot)",
        description: "Search deck for any card. Set up Boss's Orders for next turn.",
        visits: 78, visit_share: 0.10, q_value: 0.58, prior: 0.16, policy: 0.13,
        win_probability: 0.58,
        principal_variation: ["Use ability — Quick Search", "Get Boss's Orders", "Attach Energy", "End turn"],
        expected_prize_swing: 0.2,
      },
      {
        id: "a4", label: "Retreat to Pidgeot",
        description: "Tank a hit; preserve Charizard ex for a later prize swing.",
        visits: 26, visit_share: 0.04, q_value: 0.42, prior: 0.10, policy: 0.05,
        win_probability: 0.42,
        principal_variation: ["Retreat", "Pidgeot Active", "Opponent attacks", "Counter next turn"],
        expected_prize_swing: -0.3,
      },
    ],
    search_stats: {
      iterations: 789, nodes_created: 1421, cache_hit_rate: 0.78,
      iterations_per_sec: 359, avg_branching: 6.2, pv_depth: 4,
    },
  };
}

function minutesAgo(m: number) {
  return new Date(Date.now() - m * 60_000).toISOString();
}
