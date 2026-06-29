"""
Sentence-level matcher.

Takes a single cleaned sentence and tries each Rule from the registry in
priority order.  Returns the first matching Effect, or UnknownEffect if
no rule matches.

This module is intentionally thin — all pattern logic lives in patterns.py,
all structural logic lives in compiler.py.
"""

from __future__ import annotations

from loguru import logger

from src.cards.effects.models import Effect, UnknownEffect
from src.cards.effects.registry import RuleRegistry, rule_registry


def match_sentence(
    sentence: str,
    *,
    registry: RuleRegistry | None = None,
) -> Effect:
    """Match a single sentence to the first applicable Rule.

    Args:
        sentence: A cleaned, single-sentence effect text.
        registry: Registry to use (defaults to the global singleton).

    Returns:
        A typed Effect model, or UnknownEffect if nothing matched.
    """
    reg = registry or rule_registry
    rules = reg.get_rules()

    for rule in rules:
        try:
            m = rule.match(sentence)
            if m is not None:
                effect = rule.factory(m, sentence)
                logger.debug("Rule {!r} matched: {!r}", rule.name, sentence[:60])
                return effect
        except Exception as exc:
            logger.warning(
                "Rule {!r} factory raised {} for sentence {!r}",
                rule.name,
                type(exc).__name__,
                sentence[:80],
            )
            continue

    logger.debug("No rule matched sentence: {!r}", sentence[:80])
    return UnknownEffect(text=sentence, raw_text=sentence)
