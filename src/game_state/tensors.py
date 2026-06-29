"""
Tensor conversion utilities for encoded features and action masks.

NumPy is optional.  All functions have pure-Python fallbacks that return
lists or nested lists.  Import-time detection ensures the module never
hard-fails even in environments without NumPy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.game_state.encoder import EncodedFeatures
    from src.game_state.masks import ActionMask

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]
    _HAS_NUMPY = False


def has_numpy() -> bool:
    """Return True if numpy is available in the current environment."""
    return _HAS_NUMPY


# -------------------------------------------------------------------------
# Feature tensor conversion
# -------------------------------------------------------------------------

def features_to_numpy(features: EncodedFeatures) -> Any:
    """
    Convert EncodedFeatures flat vector to a 1-D numpy float32 array.
    Falls back to list[float] if numpy is unavailable.
    """
    if _HAS_NUMPY:
        return np.array(features.flat, dtype=np.float32)
    return list(features.flat)


def features_to_list(features: EncodedFeatures) -> list[float]:
    return list(features.flat)


def features_to_dict_of_arrays(features: EncodedFeatures) -> dict[str, Any]:
    """
    Return a dict mapping group name → numpy array (or list).
    Useful for feeding group-structured models.
    """
    result: dict[str, Any] = {}
    for name, vec in features.groups.items():
        if _HAS_NUMPY:
            result[name] = np.array(vec, dtype=np.float32)
        else:
            result[name] = list(vec)
    return result


def batch_features_to_numpy(feature_list: list[EncodedFeatures]) -> Any:
    """
    Stack a list of EncodedFeatures into a (N, TOTAL_FEATURE_SIZE) array.
    """
    if not feature_list:
        if _HAS_NUMPY:
            return np.empty((0, 0), dtype=np.float32)
        return []
    if _HAS_NUMPY:
        rows = [np.array(f.flat, dtype=np.float32) for f in feature_list]
        return np.stack(rows, axis=0)
    return [list(f.flat) for f in feature_list]


# -------------------------------------------------------------------------
# Mask tensor conversion
# -------------------------------------------------------------------------

def mask_to_numpy(mask: ActionMask) -> Any:
    """Convert ActionMask.as_vector to a numpy bool/float array."""
    vec = mask.as_vector
    if _HAS_NUMPY:
        return np.array(vec, dtype=np.float32)
    return list(vec)


def mask_to_list(mask: ActionMask) -> list[float]:
    return list(mask.as_vector)


def batch_masks_to_numpy(masks: list[ActionMask]) -> Any:
    """Stack a list of ActionMasks into a (N, MASK_SIZE) array."""
    if not masks:
        if _HAS_NUMPY:
            return np.empty((0, 0), dtype=np.float32)
        return []
    if _HAS_NUMPY:
        rows = [np.array(m.as_vector, dtype=np.float32) for m in masks]
        return np.stack(rows, axis=0)
    return [list(m.as_vector) for m in masks]


# -------------------------------------------------------------------------
# Combined (features + mask) batch for RL consumption
# -------------------------------------------------------------------------

def encode_transition(
    obs: EncodedFeatures,
    mask: ActionMask,
) -> dict[str, Any]:
    """
    Package a single observation + mask as a dict ready for RL consumption.

    Keys
    ----
    obs           : flat float array of shape (TOTAL_FEATURE_SIZE,)
    obs_groups    : dict of group name → array
    mask          : flat float array of shape (TOTAL_MASK_SIZE,)
    """
    return {
        "obs": features_to_numpy(obs),
        "obs_groups": features_to_dict_of_arrays(obs),
        "mask": mask_to_numpy(mask),
    }
