"""
EffectParser — the public API for converting card text into structured effects.

Usage::

    parser = EffectParser()

    # Single text → Effect
    effect = parser.parse("Draw 2 cards.")
    # DrawCards(count=2)

    # Multi-sentence text → CompositeEffect (or single if only one step)
    effect = parser.parse("Discard 2 Energy from this Pokémon. Draw 2 cards.")
    # CompositeEffect([DiscardEffect(...), DrawCards(count=2)])

    # Also available as a module-level function:
    from src.cards.effects import parse_effect
    effect = parse_effect("Flip a coin. If heads, this attack does 30 more damage.")
"""

from __future__ import annotations

import re

from src.cards.effects.matcher import match_sentence
from src.cards.effects.models import (
    CompositeEffect,
    Effect,
    UnknownEffect,
)
from src.cards.effects.registry import RuleRegistry

# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

# Patterns that look like sentence boundaries but are NOT:
# - "etc." / "e.g." / "i.e."
# - Decimal numbers "10.5"
# - Abbreviations like "No."
_NOT_BOUNDARY = re.compile(
    r"""
    (?:etc|e\.g|i\.e|No|Dr|Mr|Ms|Mrs|Prof|Vol|vs)\.   # abbreviations
    | \d\.\d                                             # decimal number
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _split_sentences(text: str) -> list[str]:
    """Split effect text into individual sentences.

    Rules:
    1. Newlines are always sentence boundaries.
    2. '. ' is a sentence boundary UNLESS preceded by an abbreviation.
    3. Bullet-point lists (•) are split into separate sentences.
    4. Parenthetical disclaimers like "(Don't apply Weakness...)" are
       stripped — they carry no action semantics.
    """
    # Normalise non-breaking spaces and other Unicode spaces
    text = text.replace("\xa0", " ").replace("　", " ")

    # Strip parenthetical rule-reminders
    _PAREN_STRIP = re.compile(
        r"\s*[\(\（]"
        r"(?:Don['']t apply Weakness and Resistance for Benched Pok[eé]mon"
        r"|Don['']t apply Weakness and Resistance"
        r"|before applying Weakness and Resistance"
        r"|after applying Weakness and Resistance"
        r"|You can choose the same Pok[eé]mon more than once"
        r"|This includes new Pok[eé]mon[^)]*"
        r")"
        r"[^)]*[\)\）]",
        re.IGNORECASE,
    )
    text = _PAREN_STRIP.sub("", text).strip()

    # Split on newlines first
    lines: list[str] = []
    for line in re.split(r"\n+", text):
        line = line.strip().lstrip("•").strip()
        if line:
            lines.append(line)

    # Within each line, split on ". " (period + space)
    sentences: list[str] = []
    for line in lines:
        # Protect abbreviations
        protected = _NOT_BOUNDARY.sub(lambda m: m.group(0).replace(".", "·"), line)
        parts = re.split(r"(?<=[.!?])\s+", protected)
        for part in parts:
            s = part.replace("·", ".").strip()
            if s:
                sentences.append(s)

    return sentences


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class EffectParser:
    """Converts raw card effect text into structured Effect models.

    Thread-safe: the registry is read-only after construction unless the
    caller explicitly adds rules.
    """

    def __init__(self, registry: RuleRegistry | None = None) -> None:
        from src.cards.effects.registry import rule_registry as _default
        self._registry = registry or _default

    def parse(self, text: str) -> Effect:
        """Parse one or more effect sentences into a single Effect.

        Returns:
            A single Effect if only one sentence was recognised,
            or a CompositeEffect if multiple sentences were parsed.
            Never raises — returns UnknownEffect on total failure.
        """
        if not text or text.strip().lower() in ("n/a", ""):
            return UnknownEffect(text=text, raw_text=text)

        sentences = _split_sentences(text)
        if not sentences:
            return UnknownEffect(text=text, raw_text=text)

        effects: list[Effect] = [
            match_sentence(s, registry=self._registry)
            for s in sentences
        ]

        # Collapse single-effect case
        if len(effects) == 1:
            return effects[0]

        return CompositeEffect(steps=tuple(effects), raw_text=text)

    def parse_all(self, texts: list[str]) -> list[Effect]:
        """Batch-parse a list of effect strings."""
        return [self.parse(t) for t in texts]


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------

_default_parser = EffectParser()


def parse_effect(text: str) -> Effect:
    """Parse a single effect string using the default global parser."""
    return _default_parser.parse(text)
