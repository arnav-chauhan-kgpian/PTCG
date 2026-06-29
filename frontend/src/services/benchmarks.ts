import type { BenchmarkSnapshot } from "@/types/api";

const BASE: Omit<BenchmarkSnapshot, "timestamp"> = {
  simulator_actions_per_sec: 10_306,
  simulator_games_per_sec: 18.0,
  encoder_per_sec: 9_591,
  network_single_latency_us: 916,
  network_batch_per_sec: 7_916,
  mcts_iterations_per_sec: 359,
  replay_samples_per_sec: 1_091_465,
};

export async function getLatestBenchmark(): Promise<BenchmarkSnapshot> {
  return { ...BASE, timestamp: new Date().toISOString() };
}

export async function getBenchmarkHistory(): Promise<BenchmarkSnapshot[]> {
  return Array.from({ length: 12 }, (_, i) => {
    const d = new Date(Date.now() - (11 - i) * 86_400_000);
    const drift = 1 + (Math.sin(i * 0.5) + Math.sin(i * 1.2)) * 0.03;
    return {
      timestamp: d.toISOString(),
      simulator_actions_per_sec: Math.round((BASE.simulator_actions_per_sec ?? 0) * drift),
      simulator_games_per_sec: +((BASE.simulator_games_per_sec ?? 0) * drift).toFixed(2),
      encoder_per_sec: Math.round((BASE.encoder_per_sec ?? 0) * drift),
      network_single_latency_us: Math.round((BASE.network_single_latency_us ?? 0) / drift),
      network_batch_per_sec: Math.round((BASE.network_batch_per_sec ?? 0) * drift),
      mcts_iterations_per_sec: Math.round((BASE.mcts_iterations_per_sec ?? 0) * drift),
      replay_samples_per_sec: Math.round((BASE.replay_samples_per_sec ?? 0) * drift),
    };
  });
}
