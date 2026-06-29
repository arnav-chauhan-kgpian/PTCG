"""
FastAPI application factory.

The server is intentionally light: it wires the existing CompetitionAgent,
deck builder, and analyser behind clean HTTP routes. No business logic
lives here.

Production-hardening properties enforced by this module:

* **Per-request agent isolation.** The loaded NetworkWrapper, CardRepository
  and Simulator are shared across requests (read-only / immutable usage).
  Every request constructs a fresh ``CompetitionAgent`` with its own
  ``MCTSSearch``, ``InferenceCache`` and search tree. No mutable search
  state is shared between concurrent requests.
* **Centralised error handling.** All exceptions are caught by the global
  handlers and returned as structured JSON. No Python traceback ever
  reaches the client.
* **Request IDs.** Every response (and every log line emitted while
  handling the request) carries an ``X-Request-ID`` header so that a
  log line can be traced back to a single request.
* **CORS.** Configurable via ``POKEMON_AI_CORS_ORIGINS`` (comma-separated;
  default empty → CORS disabled, same-origin only).
* **Timeouts.** Endpoint bodies are wrapped with a configurable per-request
  timeout (``POKEMON_AI_REQUEST_TIMEOUT_S``, default 30s).
* **Lifespan handler.** Surfaces load-time errors at server start, not at
  first request.
* **Bounded payloads.** ``n_candidates`` on ``/deck/build`` is bounded.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

try:
    from fastapi import FastAPI, HTTPException, Request, status
    from fastapi.exceptions import RequestValidationError
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, ConfigDict, Field
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from starlette.middleware.base import BaseHTTPMiddleware
    _HAS_FASTAPI = True
except ImportError:
    FastAPI = None  # type: ignore[assignment]
    HTTPException = Exception  # type: ignore[assignment]
    BaseModel = object  # type: ignore[assignment]
    def Field(*_a, **_k):  # type: ignore[no-redef] # noqa: N802
        return None
    ConfigDict = dict  # type: ignore[assignment]
    _HAS_FASTAPI = False

if TYPE_CHECKING:
    from src.cards.repository import CardRepository
    from src.competition.agent import AgentConfig, CompetitionAgent
    from src.mcts.network import NetworkWrapper

from src.logging_config import configure as _configure_logging

try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger("pokemon_ai.server")  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Server state
# ---------------------------------------------------------------------------

@dataclass
class ServerState:
    """Shared, read-only resources.

    These are loaded once at startup (or first request) and reused across
    all requests. Nothing here is mutated during request handling except
    the counter dict, which is protected by a lock.
    """
    repository: CardRepository | None = None
    network: NetworkWrapper | None = None
    agent_config: AgentConfig | None = None
    checkpoint_source: str = "none"   # "file" | "fresh" | "none"
    checkpoint_path: str | None = None
    counters: dict[str, int] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    version: str = "1.0.0"
    git_hash: str | None = None
    counter_lock: threading.Lock = field(default_factory=threading.Lock)

    def bump(self, key: str) -> None:
        with self.counter_lock:
            self.counters[key] = self.counters.get(key, 0) + 1


# Module-level state so tests can introspect it
_STATE = ServerState()


def lifespan_state() -> ServerState:
    return _STATE


def reset_state_for_tests() -> None:
    """Reset the module-level state. Test-only."""
    global _STATE
    _STATE = ServerState()


def _detect_git_hash() -> str | None:
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        pass
    return None


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

if _HAS_FASTAPI:

    class _Strict(BaseModel):
        model_config = ConfigDict(extra="forbid")

    class MoveRequest(_Strict):
        state: dict[str, Any] = Field(description="Serialised GameState dict")

    class MoveResponse(BaseModel):
        action: dict[str, Any]
        request_id: str

    class EvaluateRequest(_Strict):
        state: dict[str, Any]

    class EvaluateResponse(BaseModel):
        value: float
        perspective: int
        request_id: str

    class DeckAnalyzeRequest(_Strict):
        decklist: list[int] | str

    class DeckAnalyzeResponse(BaseModel):
        archetype: str
        consistency_grade: str
        synergy_score: float
        request_id: str

    class DeckBuildRequest(_Strict):
        seed_cards: list[str] | None = None
        archetype: str | None = None
        n_candidates: int = Field(default=1, ge=1, le=10)

    class DeckBuildResponse(BaseModel):
        ptcg_live: str
        score: float
        request_id: str

    class HealthResponse(BaseModel):
        status: str
        uptime_s: float
        agent_loaded: bool
        version: str
        git_hash: str | None = None
        checkpoint_source: str
        memory_rss_mb: float | None = None

    class MetricsResponse(BaseModel):
        counters: dict[str, int]
        agent: dict[str, Any] | None = None

    class ErrorResponse(BaseModel):
        success: bool = False
        error: str
        code: str
        request_id: str
        details: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

if _HAS_FASTAPI:

    class RequestContextMiddleware(BaseHTTPMiddleware):
        """Assign a request ID, log entry/exit, attach the ID to the response."""

        async def dispatch(self, request: Request, call_next):
            request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
            request.state.request_id = request_id
            start = time.perf_counter()
            try:
                response = await call_next(request)
            except Exception as exc:
                # Defensive: should be caught by the global handlers below,
                # but if anything slips through, log and return a structured
                # error rather than letting the framework leak a traceback.
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                logger.exception(
                    "request_failed path={} method={} request_id={} elapsed_ms={:.1f} error={}",
                    request.url.path, request.method, request_id, elapsed_ms, exc,
                )
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "error": "Internal server error",
                        "code": "internal_error",
                        "request_id": request_id,
                        "details": None,
                    },
                    headers={"X-Request-ID": request_id},
                )
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            response.headers["X-Request-ID"] = request_id
            logger.info(
                "request path={} method={} status={} request_id={} elapsed_ms={:.1f}",
                request.url.path, request.method, response.status_code,
                request_id, elapsed_ms,
            )
            return response


# ---------------------------------------------------------------------------
# Agent construction (per-request, shares immutable resources)
# ---------------------------------------------------------------------------

def _build_shared_resources(checkpoint_path: str | None) -> None:
    """Load network and repository once. Idempotent."""
    if _STATE.repository is None:
        from src.cards import load_repository
        _STATE.repository = load_repository()

    if _STATE.network is None:
        try:
            from src.competition.checkpoint_loader import CheckpointLoader
            from src.mcts.network import has_torch
            if has_torch():
                loader = CheckpointLoader()
                loaded = loader.load(checkpoint_path)
                _STATE.network = loaded.network
                _STATE.checkpoint_source = loaded.source
                _STATE.checkpoint_path = checkpoint_path
            else:
                _STATE.checkpoint_source = "no_torch"
        except (ImportError, RuntimeError, FileNotFoundError, ValueError) as exc:
            logger.warning("checkpoint_load_failed error={}", exc)
            _STATE.checkpoint_source = "fallback_heuristic"


def _build_agent_for_request() -> CompetitionAgent:
    """Fresh per-request agent. Reuses loaded network + repository + simulator,
    but gets its own MCTSSearch + InferenceCache + search tree.

    This is the cornerstone of the C2 fix: nothing mutable about the search
    is shared between concurrent requests.
    """
    from src.competition.agent import AgentConfig, CompetitionAgent
    from src.competition.inference_engine import InferenceEngine
    from src.simulator import PokemonTCGSimulator

    if _STATE.repository is None:
        from src.cards import load_repository
        _STATE.repository = load_repository()

    simulator = PokemonTCGSimulator(_STATE.repository, seed=42)
    inference = None
    if _STATE.network is not None:
        inference = InferenceEngine(_STATE.network)
    config = _STATE.agent_config or AgentConfig()
    return CompetitionAgent(simulator=simulator, inference=inference, config=config)


# ---------------------------------------------------------------------------
# Timeout helper
# ---------------------------------------------------------------------------

def _request_timeout_s() -> float:
    raw = os.getenv("POKEMON_AI_REQUEST_TIMEOUT_S", "30").strip()
    try:
        v = float(raw)
        return v if v > 0 else 30.0
    except ValueError:
        return 30.0


async def _run_with_timeout(fn, *args, **kwargs):
    """Run a blocking fn in a worker thread, enforcing a wall-clock timeout."""
    timeout = _request_timeout_s()
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, lambda: fn(*args, **kwargs)),
            timeout=timeout,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Request exceeded server timeout of {timeout:.0f}s",
        ) from exc


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app(
    *,
    checkpoint_path: str | None = None,
    repository: CardRepository | None = None,
    eager_load: bool = False,
):
    """Build and return the FastAPI app.

    The shared NetworkWrapper and CardRepository are loaded lazily on the
    first request unless ``eager_load=True``.
    """
    if not _HAS_FASTAPI:
        raise ImportError(
            "FastAPI required for the server module. pip install fastapi"
        )

    _configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        _STATE.git_hash = _STATE.git_hash or _detect_git_hash()
        if eager_load:
            try:
                _build_shared_resources(checkpoint_path)
                logger.info(
                    "server_startup_ok checkpoint_source={} version={} git={}",
                    _STATE.checkpoint_source, _STATE.version, _STATE.git_hash,
                )
            except Exception as exc:
                logger.exception("server_startup_failed error={}", exc)
                raise
        else:
            logger.info(
                "server_startup_ok lazy=True version={} git={}",
                _STATE.version, _STATE.git_hash,
            )
        yield
        # Shutdown
        logger.info(
            "server_shutdown counters={} uptime_s={:.1f}",
            dict(_STATE.counters),
            time.time() - _STATE.started_at,
        )

    app = FastAPI(
        title="Pokémon TCG AI",
        version="1.0.0",
        description="HTTP API for the Pokémon TCG AI competition agent.",
        lifespan=lifespan,
    )

    # CORS — disabled by default. Set POKEMON_AI_CORS_ORIGINS=https://x,https://y
    # to enable. "*" is allowed; we intentionally never combine "*" with
    # allow_credentials=True (per CORS spec).
    cors_raw = os.getenv("POKEMON_AI_CORS_ORIGINS", "").strip()
    if cors_raw:
        origins = [o.strip() for o in cors_raw.split(",") if o.strip()]
        allow_credentials = "*" not in origins
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=allow_credentials,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )

    app.add_middleware(RequestContextMiddleware)

    _STATE.repository = repository if repository is not None else _STATE.repository

    # ------------------------------------------------------------------ #
    # Centralised exception handlers — guarantees no traceback ever
    # reaches the client and every error response carries a request_id.
    # ------------------------------------------------------------------ #
    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", "unknown")
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": "Request validation failed",
                "code": "validation_error",
                "request_id": request_id,
                "details": {"errors": exc.errors()},
            },
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(StarletteHTTPException)
    @app.exception_handler(HTTPException)
    async def _http_exc_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", "unknown")
        code_map = {
            400: "bad_request",
            404: "not_found",
            413: "payload_too_large",
            422: "validation_error",
            504: "timeout",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": str(exc.detail),
                "code": code_map.get(exc.status_code, "http_error"),
                "request_id": request_id,
                "details": None,
            },
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(Exception)
    async def _generic_exc_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.exception(
            "unhandled_exception path={} request_id={} error={}",
            request.url.path, request_id, exc,
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "code": "internal_error",
                "request_id": request_id,
                "details": None,
            },
            headers={"X-Request-ID": request_id},
        )

    # ------------------------------------------------------------------ #
    # Routes
    # ------------------------------------------------------------------ #

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        _STATE.bump("health")
        memory_mb: float | None = None
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # Linux reports kB, macOS reports bytes
            memory_mb = usage / 1024 if usage > 1_000_000 else usage / 1024
        except Exception:
            try:
                # Best-effort Windows fallback
                import psutil  # type: ignore
                memory_mb = psutil.Process().memory_info().rss / (1024 * 1024)
            except Exception:
                memory_mb = None
        return HealthResponse(
            status="ok",
            uptime_s=round(time.time() - _STATE.started_at, 2),
            agent_loaded=_STATE.network is not None
                or _STATE.checkpoint_source in {"fresh", "fallback_heuristic", "no_torch"},
            version=_STATE.version,
            git_hash=_STATE.git_hash,
            checkpoint_source=_STATE.checkpoint_source,
            memory_rss_mb=round(memory_mb, 1) if memory_mb is not None else None,
        )

    @app.get("/metrics", response_model=MetricsResponse)
    def metrics() -> MetricsResponse:
        _STATE.bump("metrics")
        agent_summary: dict[str, Any] | None = None
        if _STATE.network is not None:
            agent_summary = {
                "num_parameters": getattr(_STATE.network, "num_parameters", 0),
                "device": getattr(_STATE.network, "device", "cpu"),
                "checkpoint_source": _STATE.checkpoint_source,
            }
        return MetricsResponse(
            counters=dict(_STATE.counters),
            agent=agent_summary,
        )

    @app.post("/move", response_model=MoveResponse)
    async def move(req: MoveRequest, request: Request) -> MoveResponse:
        _STATE.bump("move")
        request_id = request.state.request_id

        def _work() -> dict[str, Any]:
            _build_shared_resources(checkpoint_path)
            agent = _build_agent_for_request()
            return agent.choose_action_dict(req.state)

        try:
            action = await _run_with_timeout(_work)
        except HTTPException:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid game state: {exc}") from exc
        return MoveResponse(action=action, request_id=request_id)

    @app.post("/evaluate", response_model=EvaluateResponse)
    async def evaluate(req: EvaluateRequest, request: Request) -> EvaluateResponse:
        _STATE.bump("evaluate")
        request_id = request.state.request_id

        def _work() -> tuple[float, int]:
            _build_shared_resources(checkpoint_path)
            from src.game_state.serialization import from_dict
            state = from_dict(req.state)
            if _STATE.network is not None:
                from src.competition.inference_engine import InferenceEngine
                inference = InferenceEngine(_STATE.network)
                value = inference.evaluator.value_only(state)
            else:
                from src.mcts.evaluator import HeuristicEvaluator
                value, _ = HeuristicEvaluator().evaluate(state, [])
            return float(value), state.current_player

        try:
            value, perspective = await _run_with_timeout(_work)
        except HTTPException:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid game state: {exc}") from exc
        return EvaluateResponse(value=value, perspective=perspective, request_id=request_id)

    @app.post("/deck/analyze", response_model=DeckAnalyzeResponse)
    async def deck_analyze(req: DeckAnalyzeRequest, request: Request) -> DeckAnalyzeResponse:
        _STATE.bump("deck_analyze")
        request_id = request.state.request_id

        def _work():
            if _STATE.repository is None:
                from src.cards import load_repository
                _STATE.repository = load_repository()
            from src.decks.analyzer import analyze_raw
            return analyze_raw(req.decklist, _STATE.repository, name="API")

        try:
            report = await _run_with_timeout(_work)
        except HTTPException:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid decklist: {exc}") from exc
        return DeckAnalyzeResponse(
            archetype=str(report.archetype.primary_archetype),
            consistency_grade=str(report.consistency.grade),
            synergy_score=float(report.synergy.synergy_score),
            request_id=request_id,
        )

    @app.post("/deck/build", response_model=DeckBuildResponse)
    async def deck_build(req: DeckBuildRequest, request: Request) -> DeckBuildResponse:
        _STATE.bump("deck_build")
        request_id = request.state.request_id

        def _work():
            if _STATE.repository is None:
                from src.cards import load_repository
                _STATE.repository = load_repository()
            from src.cards.relationships import build_graph
            from src.deck_builder import DeckBuilder
            from src.deck_builder import exports as deck_exports
            graph = build_graph(_STATE.repository.list_all())
            builder = DeckBuilder.from_graph_and_cards(graph, _STATE.repository.list_all())
            result = builder.build(
                seed_cards=req.seed_cards,
                archetype=req.archetype,
                n_candidates=req.n_candidates,
                max_iterations=20,
                seed=0,
            )
            best = result.best
            if best is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No candidate decks generated",
                )
            return deck_exports.to_ptcg_live(best), float(best.score.total)

        try:
            ptcg_live, score = await _run_with_timeout(_work)
        except HTTPException:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid request: {exc}") from exc
        return DeckBuildResponse(
            ptcg_live=ptcg_live, score=score, request_id=request_id,
        )

    return app
