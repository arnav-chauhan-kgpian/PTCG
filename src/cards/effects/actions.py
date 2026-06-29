"""
Action tag constants used throughout the effect system.

These string constants are the canonical identifiers for every action category.
They appear in Effect.action_type and are used by downstream systems (MCTS,
feature extraction, heuristics) to dispatch on effect type without isinstance.
"""

from enum import Enum


class ActionTag(str, Enum):
    # ------------------------------------------------------------------ Card draw
    DRAW_CARDS = "draw_cards"              # draw N cards
    DRAW_UNTIL = "draw_until"             # draw until hand size N

    # ------------------------------------------------------------------ Discard
    DISCARD_ENERGY = "discard_energy"      # discard energy from a Pokémon
    DISCARD_CARDS = "discard_cards"        # discard N cards from hand/deck
    DISCARD_HAND = "discard_hand"          # discard entire hand
    DISCARD_TOOL = "discard_tool"          # discard Pokémon Tool
    DISCARD_STADIUM = "discard_stadium"    # discard Stadium in play
    DISCARD_RANDOM = "discard_random"      # random discard from opponent hand

    # ------------------------------------------------------------------ Heal
    HEAL = "heal"                          # heal N damage / heal all

    # ------------------------------------------------------------------ Deck search
    SEARCH_DECK = "search_deck"            # search deck for card(s)
    SEARCH_DISCARD = "search_discard"      # retrieve from discard pile

    # ------------------------------------------------------------------ Energy
    ATTACH_ENERGY = "attach_energy"        # attach energy from hand/discard
    MOVE_ENERGY = "move_energy"            # move energy between Pokémon
    ACCELERATE_ENERGY = "accelerate_energy"  # attach multiple energies at once

    # ------------------------------------------------------------------ Damage
    BENCH_DAMAGE = "bench_damage"          # damage to benched Pokémon
    SELF_DAMAGE = "self_damage"            # damage to self (recoil)
    DAMAGE_COUNTERS = "damage_counters"    # place N damage counters (not damage)
    VARIABLE_DAMAGE = "variable_damage"    # damage scaled by a count
    DAMAGE_MODIFIER = "damage_modifier"    # +/- damage this attack

    # ------------------------------------------------------------------ Status conditions
    INFLICT_STATUS = "inflict_status"      # Burn / Paralyzed / Poison / Asleep / Confused
    CURE_STATUS = "cure_status"            # remove special conditions
    SELF_STATUS = "self_status"            # apply status to self

    # ------------------------------------------------------------------ Board manipulation
    SWITCH_ACTIVE = "switch_active"        # switch own active
    FORCE_SWITCH = "force_switch"          # force opponent to switch
    RETURN_TO_HAND = "return_to_hand"      # return Pokémon / cards to hand
    SHUFFLE_DECK = "shuffle_deck"          # shuffle deck (or hand into deck)
    MILL = "mill"                          # discard top N cards of deck
    EVOLVE = "evolve"                      # evolve a Pokémon
    DEVOLVE = "devolve"                    # devolve a Pokémon

    # ------------------------------------------------------------------ Targeting / Knockout
    KNOCK_OUT = "knock_out"               # knock out a Pokémon directly
    PRIZE = "prize"                        # take/interact with Prize cards

    # ------------------------------------------------------------------ Prevention / Protection
    PREVENT_DAMAGE = "prevent_damage"     # prevent damage to self / bench
    PREVENT_EFFECTS = "prevent_effects"   # prevent attack effects

    # ------------------------------------------------------------------ Passive & persistent
    PASSIVE = "passive"                    # ongoing while card in play
    TRIGGERED = "triggered"               # triggers on specific game event
    END_TURN = "end_turn"                 # effect applies at end of turn

    # ------------------------------------------------------------------ Retreat / cost
    RETREAT_COST = "retreat_cost"         # modify retreat cost

    # ------------------------------------------------------------------ Suppression
    ABILITY_SUPPRESSION = "ability_suppression"  # suppress abilities

    # ------------------------------------------------------------------ Tool / Stadium
    TOOL_INTERACTION = "tool_interaction"
    STADIUM_INTERACTION = "stadium_interaction"

    # ------------------------------------------------------------------ Copy
    COPY_ATTACK = "copy_attack"           # copy an attack from another Pokémon

    # ------------------------------------------------------------------ Coin flips
    COIN_FLIP = "coin_flip"              # coin flip with conditional children

    # ------------------------------------------------------------------ Composite / structural
    COMPOSITE = "composite"               # sequence of effects
    CONDITIONAL = "conditional"           # if/unless/when wrapper
    UNKNOWN = "unknown"                   # graceful degradation


class Target(str, Enum):
    """Who is affected by an effect."""
    SELF = "self"                  # this Pokémon
    ACTIVE_SELF = "active_self"    # your Active Pokémon
    BENCHED_SELF = "benched_self"  # your Benched Pokémon(s)
    ANY_SELF = "any_self"          # any of your Pokémon
    ACTIVE_OPP = "active_opp"     # opponent's Active Pokémon
    BENCHED_OPP = "benched_opp"   # opponent's Benched Pokémon(s)
    ANY_OPP = "any_opp"           # any of opponent's Pokémon
    BOTH_ACTIVE = "both_active"   # both Active Pokémon
    BOTH_ALL = "both_all"         # all Pokémon in play


class Zone(str, Enum):
    """Card zones / locations."""
    HAND = "hand"
    DECK = "deck"
    DISCARD = "discard"
    BENCH = "bench"
    ACTIVE = "active"
    PRIZES = "prizes"
    PLAY = "play"


class Frequency(str, Enum):
    """How often an ability may be used."""
    ONCE_PER_TURN = "once_per_turn"
    AS_OFTEN_AS_LIKE = "as_often_as_like"
    PASSIVE = "passive"
    TRIGGERED = "triggered"
