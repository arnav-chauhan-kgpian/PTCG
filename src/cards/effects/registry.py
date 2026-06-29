"""
Extensible rule registry.

New rules can be added at runtime without modifying the core parser:

    from src.cards.effects.registry import rule_registry
    from src.cards.effects.patterns import Rule
    import re

    rule_registry.register(Rule(
        name="my_new_rule",
        pattern=re.compile(r"custom pattern", re.I),
        factory=lambda m, raw: MyEffect(raw_text=raw),
        priority=55,
    ))

The registry keeps rules sorted by priority at all times.
"""

from __future__ import annotations

from threading import Lock

from loguru import logger

from src.cards.effects.patterns import ALL_RULES, Rule


class RuleRegistry:
    """Thread-safe, sorted collection of parsing Rules."""

    def __init__(self) -> None:
        self._rules: list[Rule] = sorted(ALL_RULES, key=lambda r: r.priority)
        self._lock = Lock()

    def register(self, rule: Rule, *, replace: bool = False) -> None:
        """Add a new rule to the registry.

        Args:
            rule:    The Rule to add.
            replace: If True, remove any existing rule with the same name first.
        """
        with self._lock:
            if replace:
                self._rules = [r for r in self._rules if r.name != rule.name]
            elif any(r.name == rule.name for r in self._rules):
                logger.warning("Rule {!r} already registered; skipping (pass replace=True to override)", rule.name)
                return
            self._rules.append(rule)
            self._rules.sort(key=lambda r: r.priority)
            logger.debug("Registered rule {!r} at priority {}", rule.name, rule.priority)

    def unregister(self, name: str) -> bool:
        """Remove a rule by name. Returns True if the rule was found."""
        with self._lock:
            before = len(self._rules)
            self._rules = [r for r in self._rules if r.name != name]
            removed = len(self._rules) < before
            if removed:
                logger.debug("Unregistered rule {!r}", name)
            return removed

    def get_rules(self) -> list[Rule]:
        """Return a snapshot of the current rule list (sorted by priority)."""
        with self._lock:
            return list(self._rules)

    def names(self) -> list[str]:
        with self._lock:
            return [r.name for r in self._rules]

    def __len__(self) -> int:
        return len(self._rules)


# Global singleton — importable by all modules
rule_registry = RuleRegistry()
