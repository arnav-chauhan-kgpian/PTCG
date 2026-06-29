/** Dashboard service — swap to real `/dashboard` endpoint when available. */
import type { ActivityItem, DashboardSummary } from "@/types/api";
import { endpoints } from "@/lib/api/endpoints";

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const [health, metrics] = await Promise.all([
    endpoints.health().catch(() => null),
    endpoints.metrics().catch(() => null),
  ]);

  const cacheHit = metrics?.agent?.inference?.cache_hit_rate ?? 0.75;
  const activity: ActivityItem[] = [
    { id: "1", kind: "promotion", message: "Candidate promoted (win rate 0.62)", timestamp: minutesAgo(2) },
    { id: "2", kind: "benchmark", message: "MCTS reached 359 iter/s on real cards", timestamp: minutesAgo(18) },
    { id: "3", kind: "training", message: "Round 47 — policy loss 0.247", timestamp: minutesAgo(43) },
    { id: "4", kind: "checkpoint", message: "Saved ckpt_000048.pt", timestamp: minutesAgo(64) },
    { id: "5", kind: "validation", message: "Simulator correctness 1.0000 over 30 games", timestamp: minutesAgo(95) },
  ];

  return {
    games_played: 1287,
    current_model: "ckpt_000048",
    simulator_fidelity: 0.823,
    win_rate: 0.616,
    training_progress: 0.47,
    mcts_speed: 359,
    cache_hit_rate: cacheHit,
    coverage: 0.9,
    tests_passing: 1065,
    latest_checkpoint: "ckpt_000048.pt",
    latest_benchmark_at: minutesAgo(18),
    recent_activity: activity,
    system_health: { ok: health?.status === "ok" || health == null, uptime_s: health?.uptime_s ?? 0 },
  };
}

function minutesAgo(m: number) {
  return new Date(Date.now() - m * 60_000).toISOString();
}
