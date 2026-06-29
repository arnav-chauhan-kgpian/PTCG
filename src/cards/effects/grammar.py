"""
Shared grammar fragments used across multiple pattern rules.

Every fragment is a raw regex string (no compiled objects here).
Caller compiles patterns lazily via patterns.py.

Naming convention:
  _NUM   — matches a cardinal number word or digit sequence
  _PTYPE — matches {G}/{R}/... energy type symbols
  _TGT   — common target phrases
  _ANY   — "any" qualifier
"""

from __future__ import annotations

# ---- Number words and digits -----------------------------------------------

# Matches "1", "2", ..., "10", "a", "an" (for "a card", "an Energy")
NUM_WORD = r"(?:1|2|3|4|5|6|7|8|9|10|a|an|one|two|three|four|five|six|seven|eight|nine|ten)"

# Digits only
NUM_DIGIT = r"\d+"

# "up to N" or "up to N more"
UP_TO_N = r"up to (?P<count>" + NUM_DIGIT + r")"

# ---- Energy type symbols ---------------------------------------------------
ENERGY_TYPE = r"(?:\{G\}|\{R\}|\{W\}|\{L\}|\{P\}|\{F\}|\{D\}|\{M\}|\{C\}|竜)"

# ---- Common target phrases -------------------------------------------------

OPPONENT_ACTIVE = r"your opponent['']s Active Pok[eé]mon"
OPPONENT_BENCHED = r"your opponent['']s Benched Pok[eé]mon"
OPPONENT_ANY = r"your opponent['']s Pok[eé]mon"

YOUR_SELF = r"this Pok[eé]mon"
YOUR_ACTIVE = r"your Active Pok[eé]mon"
YOUR_BENCHED = r"your Benched Pok[eé]mon"
YOUR_ANY = r"(?:1 of your|your) Pok[eé]mon"

# ---- Status condition names ------------------------------------------------
STATUS_NAME = r"(?:Burned|Paralyzed|Poisoned|Asleep|Confused)"

# ---- Common clauses --------------------------------------------------------
THEN_SHUFFLE = r"(?:Then,?\s+)?shuffle (?:your|their) deck"
REVEAL_IT = r"reveal (?:it|them)"
PUT_INTO_HAND = r"put (?:it|them) into (?:your|their) hand"

# ---- "Don't apply Weakness" disclaimer ------------------------------------
NO_WEAK_RES = (
    r"\s*[\(\（][Dd]on['']t apply "
    r"(?:Weakness and Resistance|Weakness|Resistance)[^)]*[\)\）]"
)

# ---- Parenthetical notes (typically rules clarifications) ------------------
PAREN_NOTE = r"\s*[\(\（][^\)）]{1,200}[\)\）]"

# ---- "Before applying Weakness and Resistance" clause ---------------------
BEFORE_WR = r"\s*\(?before applying Weakness and Resistance\)?"

# ---- "After applying Weakness and Resistance" clause ----------------------
AFTER_WR = r"\s*\(?after applying Weakness and Resistance\)?"
