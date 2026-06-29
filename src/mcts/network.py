"""
Joint policy + value network wrapper.

A single forward pass produces both policy logits and a scalar value, the
canonical AlphaZero output.  This module owns the PyTorch model lifecycle:

  • build / instantiate a network
  • load / save state dicts and checkpoints
  • move between CPU and GPU
  • optional TorchScript compilation
  • optional mixed-precision inference

Importable without PyTorch installed: the lightweight ``NetworkConfig``
dataclass and ``has_torch()`` flag are always available.  Model
construction raises a clear ImportError if torch is missing.
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import torch
    from torch import nn
    _HAS_TORCH = True
except ImportError:
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    _HAS_TORCH = False


def has_torch() -> bool:
    return _HAS_TORCH


# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class NetworkConfig:
    """Architecture and runtime configuration for the joint network."""

    input_size: int = 741                # Phase 7 TOTAL_FEATURE_SIZE
    action_size: int = 256               # max distinct actions per state
    hidden_size: int = 256
    num_hidden_layers: int = 2
    dropout: float = 0.0
    use_layernorm: bool = True
    activation: str = "relu"             # "relu" | "gelu" | "tanh"
    device: str = "auto"                 # "auto" | "cpu" | "cuda" | "cuda:0"
    use_mixed_precision: bool = False
    torchscript: bool = False

    def resolve_device(self) -> str:
        if self.device != "auto":
            return self.device
        if _HAS_TORCH and torch.cuda.is_available():
            return "cuda"
        return "cpu"


# -------------------------------------------------------------------------
# Architecture
# -------------------------------------------------------------------------

if _HAS_TORCH:

    def _activation(name: str):
        return {
            "relu": nn.ReLU,
            "gelu": nn.GELU,
            "tanh": nn.Tanh,
        }.get(name, nn.ReLU)()

    class _MLPBlock(nn.Module):
        def __init__(self, in_size: int, out_size: int, dropout: float, use_ln: bool, activation: str):
            super().__init__()
            self.linear = nn.Linear(in_size, out_size)
            self.norm = nn.LayerNorm(out_size) if use_ln else nn.Identity()
            self.act = _activation(activation)
            self.drop = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

        def forward(self, x):
            return self.drop(self.act(self.norm(self.linear(x))))

    class JointNetwork(nn.Module):
        """
        Two-headed network: shared MLP trunk → policy head + value head.

        Output
        ------
        policy_logits : (batch, action_size)
        value         : (batch, 1) bounded to [0, 1] via sigmoid
        """

        def __init__(self, config: NetworkConfig):
            super().__init__()
            self.config = config

            layers = [_MLPBlock(
                config.input_size, config.hidden_size,
                config.dropout, config.use_layernorm, config.activation,
            )]
            for _ in range(config.num_hidden_layers - 1):
                layers.append(_MLPBlock(
                    config.hidden_size, config.hidden_size,
                    config.dropout, config.use_layernorm, config.activation,
                ))
            self.trunk = nn.Sequential(*layers)

            self.policy_head = nn.Linear(config.hidden_size, config.action_size)
            self.value_head = nn.Sequential(
                nn.Linear(config.hidden_size, config.hidden_size // 2),
                _activation(config.activation),
                nn.Linear(config.hidden_size // 2, 1),
            )

        def forward(self, x):
            trunk = self.trunk(x)
            policy_logits = self.policy_head(trunk)
            value = torch.sigmoid(self.value_head(trunk))
            return policy_logits, value

else:
    JointNetwork = None  # type: ignore[assignment]


# -------------------------------------------------------------------------
# Wrapper
# -------------------------------------------------------------------------

class NetworkWrapper:
    """
    High-level container that owns a JointNetwork plus runtime utilities.

    All inference is performed with ``torch.no_grad()`` and the model in
    eval mode.  ``predict(features)`` returns numpy arrays / tuples to
    keep the rest of MCTS torch-free.
    """

    def __init__(
        self,
        config: NetworkConfig,
        model: nn.Module | None = None,
    ) -> None:
        if not _HAS_TORCH:
            raise ImportError("PyTorch is required for NetworkWrapper")

        self.config = config
        self.device = config.resolve_device()
        self.model: nn.Module = model if model is not None else JointNetwork(config)
        self.model.to(self.device)
        self.model.eval()

        if config.torchscript:
            try:
                example = torch.zeros(1, config.input_size, device=self.device)
                self.model = torch.jit.trace(self.model, example)
            except Exception:
                pass  # fall back silently to eager mode

    # ------------------------------------------------------------------ #
    # Inference
    # ------------------------------------------------------------------ #

    def predict(self, features: tuple[float, ...]):
        """Single-state inference. Returns (policy_logits, value) as tuples."""
        logits, value = self.predict_batch([features])
        return logits[0], value[0]

    def predict_batch(self, batch: list[tuple[float, ...]]):
        """Batched inference. Returns (logits_batch, value_batch)."""
        if not batch:
            return [], []
        with torch.no_grad():
            x = torch.tensor(batch, dtype=torch.float32, device=self.device)
            if self.config.use_mixed_precision and self.device.startswith("cuda"):
                with torch.autocast(device_type="cuda"):
                    logits, values = self.model(x)
            else:
                logits, values = self.model(x)
            logits_np = logits.detach().cpu().tolist()
            values_np = [float(v[0]) for v in values.detach().cpu().tolist()]
        return logits_np, values_np

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def state_dict(self):
        return self.model.state_dict()

    def load_state_dict(self, state_dict, strict: bool = True):
        self.model.load_state_dict(state_dict, strict=strict)
        self.model.eval()

    def save(self, path: str) -> None:
        torch.save({
            "config": self.config.__dict__,
            "model_state": self.model.state_dict(),
        }, path)

    @classmethod
    def load(cls, path: str, device: str = "auto") -> NetworkWrapper:
        import pathlib
        p = pathlib.Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Checkpoint not found: {p}")
        if p.suffix != ".pt":
            raise ValueError(f"Refusing to load non-.pt checkpoint: {p}")
        # weights_only=True restricts unpickling to safe tensor types only,
        # preventing arbitrary code execution from a malicious checkpoint.
        payload = torch.load(p, map_location="cpu", weights_only=True)
        cfg_dict = dict(payload["config"])
        if device != "auto":
            cfg_dict["device"] = device
        cfg = NetworkConfig(**cfg_dict)
        wrapper = cls(cfg)
        wrapper.load_state_dict(payload["model_state"])
        return wrapper

    # ------------------------------------------------------------------ #
    # Device movement
    # ------------------------------------------------------------------ #

    def to(self, device: str) -> NetworkWrapper:
        self.device = device
        self.model.to(device)
        return self

    @property
    def num_parameters(self) -> int:
        return sum(p.numel() for p in self.model.parameters())


# -------------------------------------------------------------------------
# Convenience constructors
# -------------------------------------------------------------------------

def make_network(config: NetworkConfig | None = None) -> NetworkWrapper:
    """Convenience factory for a fresh randomly-initialised network."""
    return NetworkWrapper(config or NetworkConfig())
