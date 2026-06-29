import type {
  DeckAnalyzeRequest,
  DeckAnalyzeResponse,
  DeckBuildRequest,
  DeckBuildResponse,
  EvaluateRequest,
  EvaluateResponse,
  HealthResponse,
  MetricsResponse,
  MoveRequest,
  MoveResponse,
} from "@/types/api";
import { api } from "./client";

export const endpoints = {
  health: () => api.get<HealthResponse>("/health"),
  metrics: () => api.get<MetricsResponse>("/metrics"),
  move: (body: MoveRequest) => api.post<MoveResponse>("/move", body),
  evaluate: (body: EvaluateRequest) => api.post<EvaluateResponse>("/evaluate", body),
  deckAnalyze: (body: DeckAnalyzeRequest) =>
    api.post<DeckAnalyzeResponse>("/deck/analyze", body),
  deckBuild: (body: DeckBuildRequest) =>
    api.post<DeckBuildResponse>("/deck/build", body),
};
