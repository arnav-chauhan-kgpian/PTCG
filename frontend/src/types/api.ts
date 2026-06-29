// Types for the Pokémon AI backend (FastAPI).

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
  uptime_s: number;
  agent_loaded: boolean;
}

export interface MetricsResponse {
  counters: Record<string, number>;
  agent: null | {
    config: Record<string, unknown>;
    inference: null | {
      num_parameters: number;
      device: string;
      cache_size: number;
      cache_hit_rate: number;
    };
  };
}

export interface MoveRequest {
  state: Record<string, unknown>;
}
export interface MoveResponse {
  action: { action_type: string; details: Record<string, string> };
}

export interface EvaluateRequest {
  state: Record<string, unknown>;
}
export interface EvaluateResponse {
  value: number;
  perspective: number;
}

export interface DeckAnalyzeRequest {
  decklist: string | number[];
}
export interface DeckAnalyzeResponse {
  archetype: string;
  consistency_grade: string;
  synergy_score: number;
}

export interface DeckBuildRequest {
  seed_cards?: string[] | null;
  archetype?: string | null;
  n_candidates?: number;
}
export interface DeckBuildResponse {
  ptcg_live: string;
  score: number;
}

// Dashboard / training / benchmark synthetic types — backend can be extended later.
export interface DashboardSummary {
  games_played: number;
  current_model: string;
  simulator_fidelity: number;
  win_rate: number;
  training_progress: number;
  mcts_speed: number;
  cache_hit_rate: number;
  coverage: number;
  tests_passing: number;
  latest_checkpoint: string;
  latest_benchmark_at: string;
  recent_activity: ActivityItem[];
  system_health: { ok: boolean; uptime_s: number };
}

export interface ActivityItem {
  id: string;
  kind: "training" | "promotion" | "benchmark" | "checkpoint" | "validation";
  message: string;
  timestamp: string;
}

export interface TrainingMetrics {
  steps: { step: number; total_loss: number; policy_loss: number; value_loss: number }[];
  arena: { round: number; win_rate: number; elo: number }[];
  promotions: { round: number; win_rate: number; score: number; reason: string }[];
  replay_size: number;
  learning_rate: number;
  throughput_samples_per_sec: number;
}

export interface BenchmarkSnapshot {
  timestamp: string;
  simulator_actions_per_sec: number | null;
  simulator_games_per_sec: number | null;
  encoder_per_sec: number | null;
  network_single_latency_us: number | null;
  network_batch_per_sec: number | null;
  mcts_iterations_per_sec: number | null;
  replay_samples_per_sec: number | null;
}

export interface SimulatorCoverage {
  trainers_total: number;
  trainers_supported: number;
  trainer_coverage: number;
  attacks_total: number;
  attacks_supported: number;
  attack_coverage: number;
  abilities_total: number;
  abilities_supported: number;
  ability_coverage: number;
}

export interface CardSummary {
  card_id: number;
  name: string;
  category: "Pokémon" | "Trainer" | "Energy";
  pokemon_type?: string;
  stage?: string;
  hp?: number;
  rule_box?: string;
  expansion?: string;
  collection_number?: string;
  ability_name?: string;
  weakness?: string;
  resistance?: string;
  retreat_cost?: number;
  attacks?: { name: string; cost: string[]; damage: number; effect?: string }[];
  effect?: string;
}
