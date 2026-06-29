"""
FastAPI server exposing the agent over HTTP.

Endpoints
---------
POST /move           — choose an action for a supplied game state
POST /evaluate       — return current player's win-probability estimate
POST /deck/analyze   — analyse a deck list
POST /deck/build     — build a 60-card deck around seeds/type/archetype
GET  /health         — liveness probe
GET  /metrics        — counters + cache hit-rate

Usage::

    from src.server import create_app
    app = create_app()                 # FastAPI app object
"""

from src.server.app import create_app, lifespan_state

__all__ = ["create_app", "lifespan_state"]
