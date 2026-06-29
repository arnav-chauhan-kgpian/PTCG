"""
Callback system for the Trainer.

A ``Callback`` is a passive observer with hooks invoked at key moments in
the training pipeline.  Callbacks may not mutate Trainer state; they
should log, snapshot, or trigger side effects.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Callback(Protocol):
    def on_training_start(self, context: dict) -> None: ...
    def on_round_start(self, context: dict) -> None: ...
    def on_selfplay_end(self, context: dict) -> None: ...
    def on_train_step(self, context: dict) -> None: ...
    def on_epoch_end(self, context: dict) -> None: ...
    def on_checkpoint(self, context: dict) -> None: ...
    def on_evaluation(self, context: dict) -> None: ...
    def on_promotion(self, context: dict) -> None: ...
    def on_round_end(self, context: dict) -> None: ...
    def on_exception(self, context: dict) -> None: ...
    def on_training_end(self, context: dict) -> None: ...


class BaseCallback:
    """Default no-op implementations for every hook."""
    def on_training_start(self, context: dict) -> None: pass
    def on_round_start(self, context: dict) -> None: pass
    def on_selfplay_end(self, context: dict) -> None: pass
    def on_train_step(self, context: dict) -> None: pass
    def on_epoch_end(self, context: dict) -> None: pass
    def on_checkpoint(self, context: dict) -> None: pass
    def on_evaluation(self, context: dict) -> None: pass
    def on_promotion(self, context: dict) -> None: pass
    def on_round_end(self, context: dict) -> None: pass
    def on_exception(self, context: dict) -> None: pass
    def on_training_end(self, context: dict) -> None: pass


class CallbackList(BaseCallback):
    """Fan out hook calls to a list of callbacks; isolate exceptions."""

    def __init__(self, callbacks: list[Callback] | None = None) -> None:
        self.callbacks: list[Callback] = list(callbacks or [])

    def add(self, cb: Callback) -> None:
        self.callbacks.append(cb)

    def _dispatch(self, hook: str, context: dict) -> None:
        for cb in self.callbacks:
            fn = getattr(cb, hook, None)
            if fn is None:
                continue
            try:
                fn(context)
            except Exception as exc:  # callbacks must never break training
                last = self.callbacks[-1] if self.callbacks else None
                if last is not cb and hasattr(last, "on_exception"):
                    try:
                        last.on_exception({"hook": hook, "error": str(exc)})
                    except Exception:
                        pass

    def on_training_start(self, context): self._dispatch("on_training_start", context)
    def on_round_start(self, context): self._dispatch("on_round_start", context)
    def on_selfplay_end(self, context): self._dispatch("on_selfplay_end", context)
    def on_train_step(self, context): self._dispatch("on_train_step", context)
    def on_epoch_end(self, context): self._dispatch("on_epoch_end", context)
    def on_checkpoint(self, context): self._dispatch("on_checkpoint", context)
    def on_evaluation(self, context): self._dispatch("on_evaluation", context)
    def on_promotion(self, context): self._dispatch("on_promotion", context)
    def on_round_end(self, context): self._dispatch("on_round_end", context)
    def on_exception(self, context): self._dispatch("on_exception", context)
    def on_training_end(self, context): self._dispatch("on_training_end", context)


# -------------------------------------------------------------------------
# Built-in callbacks
# -------------------------------------------------------------------------

class LoggingCallback(BaseCallback):
    """Pipes hook contexts into a ``MetricLogger``."""

    def __init__(self, logger) -> None:
        self.logger = logger

    def on_training_start(self, context):
        self.logger.log("training_start", context, force=True)

    def on_train_step(self, context):
        self.logger.log("train_step", context)

    def on_selfplay_end(self, context):
        self.logger.log("selfplay", context)

    def on_round_end(self, context):
        self.logger.log("round_end", context, force=True)

    def on_evaluation(self, context):
        self.logger.log("evaluation", context, force=True)

    def on_promotion(self, context):
        self.logger.log("promotion", context, force=True)

    def on_checkpoint(self, context):
        self.logger.log("checkpoint", context, force=True)

    def on_training_end(self, context):
        self.logger.log("training_end", context, force=True)
        if hasattr(self.logger, "close"):
            self.logger.close()


class HistoryCallback(BaseCallback):
    """Records every hook invocation in an in-memory list (for tests)."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def _record(self, hook: str, context: dict) -> None:
        self.events.append((hook, dict(context)))

    def on_training_start(self, context): self._record("on_training_start", context)
    def on_round_start(self, context): self._record("on_round_start", context)
    def on_selfplay_end(self, context): self._record("on_selfplay_end", context)
    def on_train_step(self, context): self._record("on_train_step", context)
    def on_epoch_end(self, context): self._record("on_epoch_end", context)
    def on_checkpoint(self, context): self._record("on_checkpoint", context)
    def on_evaluation(self, context): self._record("on_evaluation", context)
    def on_promotion(self, context): self._record("on_promotion", context)
    def on_round_end(self, context): self._record("on_round_end", context)
    def on_exception(self, context): self._record("on_exception", context)
    def on_training_end(self, context): self._record("on_training_end", context)

    def count(self, hook: str) -> int:
        return sum(1 for h, _ in self.events if h == hook)
