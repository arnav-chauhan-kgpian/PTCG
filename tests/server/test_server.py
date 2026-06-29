"""Smoke + production-hardening tests for the FastAPI server."""

from __future__ import annotations

import pathlib

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient
from src.cards.enums import (
    CardSuperType,
    DamageModifier,
    EnergyType,
    ExpansionCode,
    PokemonType,
    Stage,
)
from src.cards.models import (
    Attack,
    DamageValue,
    EnergyCard,
    EnergyCostModel,
    PokemonCard,
)
from src.cards.parser import ParseResult
from src.cards.repository import CardRepository

_ID = 7_000_000


def _next_id() -> int:
    global _ID
    _ID += 1
    return _ID


def _basic() -> PokemonCard:
    return PokemonCard(
        card_id=_next_id(), name="Mon",
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.POKEMON,
        stage=Stage.BASIC, hp=80, pokemon_type=PokemonType.COLORLESS,
        attacks=(Attack(
            name="Tackle",
            cost=EnergyCostModel(tokens=("{C}",), total_count=1),
            damage=DamageValue(base=20, modifier=DamageModifier.EXACT, raw="20"),
        ),),
        retreat_cost=1,
    )


def _energy() -> EnergyCard:
    return EnergyCard(
        card_id=_next_id(), name="C Energy",
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.ENERGY,
        energy_type=EnergyType.BASIC, provides=(PokemonType.COLORLESS,),
    )


@pytest.fixture
def client():
    from src.server import create_app
    from src.server.app import reset_state_for_tests
    reset_state_for_tests()
    repo = CardRepository(
        ParseResult(cards=[_basic(), _energy()]),
        run_validation=False,
    )
    app = create_app(repository=repo)
    return TestClient(app)


class TestServer:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        # Enhanced health payload (P1 hardening)
        assert "version" in body
        assert "uptime_s" in body
        assert "checkpoint_source" in body
        assert "agent_loaded" in body
        # Request ID is present on every response
        assert "X-Request-ID" in r.headers

    def test_metrics(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        assert "counters" in r.json()
        assert "X-Request-ID" in r.headers

    def test_openapi(self, client):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        body = r.json()
        assert body["info"]["title"] == "Pokémon TCG AI"


# ------------------------------------------------------------------ #
# Production hardening regression tests
# ------------------------------------------------------------------ #


class TestRequestIDs:
    """Every response — including errors — carries a request_id."""

    def test_request_id_header_generated(self, client):
        r = client.get("/health")
        assert "X-Request-ID" in r.headers
        assert len(r.headers["X-Request-ID"]) >= 8

    def test_request_id_propagated_from_client(self, client):
        r = client.get("/health", headers={"X-Request-ID": "test-abc-123"})
        assert r.headers["X-Request-ID"] == "test-abc-123"

    def test_request_id_unique_per_request(self, client):
        ids = {client.get("/health").headers["X-Request-ID"] for _ in range(5)}
        assert len(ids) == 5


class TestExceptionHandling:
    """No raw Python tracebacks ever reach the client (C4)."""

    def test_404_returns_structured_json(self, client):
        r = client.get("/this-route-does-not-exist")
        assert r.status_code == 404
        body = r.json()
        # Structured JSON, not a default FastAPI {"detail": ...}
        assert body.get("success") is False
        assert body.get("code") == "not_found"
        assert "request_id" in body

    def test_malformed_state_never_leaks_traceback(self, client):
        # The /move endpoint may gracefully handle bogus state (returning a
        # fallback action) or reject with 4xx. Either is acceptable — the
        # invariant being enforced is "no Python traceback ever reaches
        # the client" regardless of code path.
        r = client.post("/move", json={"state": {"this_is_not": "a_real_state"}})
        text = r.text
        assert "Traceback" not in text
        assert 'File "' not in text
        assert r.status_code in {200, 400, 422, 500, 504}

    def test_extra_fields_rejected_on_move(self, client):
        # extra="forbid" on request models — unknown fields are validation errors
        r = client.post("/move", json={"state": {}, "unexpected_field": 1})
        assert r.status_code in {400, 422}

    def test_n_candidates_upper_bound_enforced(self, client):
        # H7 regression — DoS via huge n_candidates
        r = client.post(
            "/deck/build",
            json={"archetype": None, "seed_cards": None, "n_candidates": 1_000_000},
        )
        assert r.status_code == 422
        body = r.json()
        assert body.get("success") is False


class TestHealthPayload:
    """Enhanced /health surface (P1)."""

    def test_health_includes_version_and_source(self, client):
        body = client.get("/health").json()
        assert body["version"] == "1.0.0"
        assert body["checkpoint_source"] in {
            "none", "fresh", "file", "fallback_heuristic", "no_torch",
        }


class TestPerRequestIsolation:
    """C2 regression — concurrent requests must not share mutable search state."""

    def test_health_concurrent_safe(self, client):
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(lambda: client.get("/health")) for _ in range(8)]
            results = [f.result() for f in futures]
        assert all(r.status_code == 200 for r in results)
        # Each response carries its own request_id
        ids = {r.headers["X-Request-ID"] for r in results}
        assert len(ids) == 8

    def test_no_shared_agent_state_module_attribute(self):
        """Module no longer exposes a single shared CompetitionAgent."""
        from src.server import app as app_module
        # The module-level state should hold immutable resources only
        # (network, repository) — never a mutable per-request CompetitionAgent.
        state = app_module.lifespan_state()
        assert not hasattr(state, "agent") or state.__class__.__name__ == "ServerState"
        # The new ServerState should carry network instead of agent
        assert hasattr(state, "network")


class TestDockerIgnorePresent:
    """C1 regression — .dockerignore exists and excludes the big hitters."""

    def test_dockerignore_exists(self):
        root = pathlib.Path(__file__).resolve().parents[2]
        dockerignore = root / ".dockerignore"
        assert dockerignore.exists(), "Production .dockerignore missing"
        text = dockerignore.read_text(encoding="utf-8")
        for must_exclude in [
            "venv", ".venv", ".git", ".pytest_cache", "node_modules",
            "__pycache__", "*.pdf", "frontend",
        ]:
            assert must_exclude in text, f"{must_exclude} not in .dockerignore"


class TestCheckpointSafety:
    """C3 regression — checkpoint loaders refuse non-.pt and non-existent paths."""

    def test_network_load_rejects_missing_file(self, tmp_path):
        pytest.importorskip("torch")
        from src.mcts.network import NetworkWrapper
        with pytest.raises(FileNotFoundError):
            NetworkWrapper.load(str(tmp_path / "does_not_exist.pt"))

    def test_network_load_rejects_wrong_suffix(self, tmp_path):
        pytest.importorskip("torch")
        bogus = tmp_path / "evil.pkl"
        bogus.write_bytes(b"not a real checkpoint")
        from src.mcts.network import NetworkWrapper
        with pytest.raises(ValueError):
            NetworkWrapper.load(str(bogus))

    def test_checkpoint_manager_load_rejects_missing(self, tmp_path):
        pytest.importorskip("torch")
        from src.mcts.checkpoints import CheckpointManager
        mgr = CheckpointManager(tmp_path)
        with pytest.raises(FileNotFoundError):
            mgr.load("ckpt_does_not_exist")
