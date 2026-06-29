import type { TrainingMetrics } from "@/types/api";

export async function getTrainingMetrics(): Promise<TrainingMetrics> {
  const steps = Array.from({ length: 60 }, (_, i) => {
    const t = i / 60;
    const base = 2.4 - 1.9 * (1 - Math.exp(-3.4 * t));
    const noise = (Math.sin(i * 0.43) * 0.08 + Math.sin(i * 0.91) * 0.05);
    return {
      step: i * 50,
      total_loss: +(base + noise).toFixed(4),
      policy_loss: +(base * 0.62 + noise * 0.3).toFixed(4),
      value_loss: +(base * 0.38 + noise * 0.2).toFixed(4),
    };
  });
  const arena = Array.from({ length: 24 }, (_, i) => {
    const eloBase = 1500 + i * 22 + Math.sin(i * 0.7) * 18;
    return {
      round: i + 1,
      win_rate: clamp01(0.42 + i * 0.012 + Math.sin(i * 0.5) * 0.04),
      elo: Math.round(eloBase),
    };
  });
  const promotions = [
    { round: 7, win_rate: 0.58, score: 0.59, reason: "score 0.59 ≥ 0.55" },
    { round: 14, win_rate: 0.62, score: 0.63, reason: "score 0.63 ≥ 0.55" },
    { round: 22, win_rate: 0.61, score: 0.61, reason: "score 0.61 ≥ 0.55" },
  ];
  return {
    steps,
    arena,
    promotions,
    replay_size: 84_731,
    learning_rate: 0.0007,
    throughput_samples_per_sec: 1_091_465,
  };
}

function clamp01(x: number) {
  return Math.max(0, Math.min(1, x));
}
