import math
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
from copy import deepcopy

from shared.schemas import (
    GameState, UnitState, Order, OrderType, HexCoord,
    GameStatus, Event, CombatDetails, UnitType
)
from shared.hex_math import Hex, hex_neighbors

# --- Constants ---
DEF_CONSTANT = 25
TERRAIN_DEF_BONUS = {
    "Plains": 0, "Hills": 10, "Forest": 20,
    "City": 0, "Mountain": 0, "Water": 0
}
TERRAIN_MOVE_COST = {
    "Plains": 1, "Hills": 2, "Forest": 2,
    "City": 1, "Mountain": 999, "Water": 999
}

class GameEngine:
    """
    Deterministic State Machine.
    Input: Current State + List of Orders
    Output: Next State
    """

    def __init__(self, match_id: str):
        self.match_id = match_id

    def process_tick(self, state: GameState, orders: List[Order]) -> GameState:
        """
        Main Simulation Step (The "Tick").
        """
        next_state = deepcopy(state)
        next_state.tick += 1
        next_state.events = [] # Clear old events

        # 1. Indexing for O(1) lookups
        units_by_id = {u.id: u for u in next_state.you.units} # In a real game, merge all players' units
        unit_positions = defaultdict(list)
        for u in next_state.you.units: # Assuming 'you' contains all units for this engine context
            unit_positions[Hex(u.q, u.r)].append(u)

        # 2. Validate & Filter Orders
        move_orders = [o for o in orders if o.type == OrderType.MOVE and o.id in units_by_id]

        # 3. Movement Resolution ("Lock & Bounce")
        self._resolve_movement(next_state, move_orders, units_by_id, unit_positions)

        # 4. Combat Resolution ("EHP Model")
        self._resolve_combat(next_state, unit_positions)

        return next_state

    # --- 2.4 Movement Logic ---

    def _resolve_movement(self, state: GameState, move_orders: List[Order],
                          units_by_id: Dict[str, UnitState],
                          unit_positions: Dict[Hex, List[UnitState]]):

        # Track intentions: unit_id -> Target Hex
        intentions: Dict[str, Hex] = {}
        # Track current location: unit_id -> Origin Hex
        origins: Dict[str, Hex] = {}

        for order in move_orders:
            unit = units_by_id[order.id]
            target = Hex(order.dest.q, order.dest.r)
            origin = Hex(unit.q, unit.r)

            # Basic Validation (Cost, Range)
            # In a full impl, check Move Cost vs Unit MP here.
            # Assuming valid for this snippet.
            intentions[unit.id] = target
            origins[unit.id] = origin

        # --- Phase A: Conflict (Multiple units target same empty/friendly hex) ---
        # Group by target
        targets_map = defaultdict(list)
        for uid, target in intentions.items():
            targets_map[target].append(uid)

        bounced_units = set()

        for target, uids in targets_map.items():
            if len(uids) > 1:
                # Calculate Initiative: (CurrentMP * 1000) + Unit_ID_Hash
                # We use hash(id) for deterministic integer conversion
                # Note: Spec says Unit ID Integer. We simulate with hash.
                uids.sort(key=lambda x: (units_by_id[x].mp * 1000) + abs(hash(x)), reverse=True)

                winner = uids[0]
                losers = uids[1:]

                # Mark losers as bounced
                for l in losers:
                    bounced_units.add(l)

        # --- Phase B: Collision (Head-to-Head Swap) ---
        # If A->B and B->A, and they are enemies.
        # For this logic, we assume all units in 'state' are loaded.
        # We check if intentions form a cycle of length 2 between enemies.

        for uid, target in intentions.items():
            if uid in bounced_units: continue

            # Check who is currently at the target
            occupiers = unit_positions.get(target, [])
            for occ in occupiers:
                # Is the occupier trying to move to MY origin?
                if occ.id in intentions and intentions[occ.id] == origins[uid]:
                    # Determine hostility (simplify: different owners)
                    if occ.owner != units_by_id[uid].owner:
                        # HEAD-TO-HEAD COLLISION
                        bounced_units.add(uid)
                        bounced_units.add(occ.id)
                        # Spec: "Immediate Combat" (handled in Combat Phase by adjacency)

        # --- Phase C: Chain Dependency ---
        # If A moves to Y, but Occupier of Y bounced or didn't move -> A bounces.
        # Iterate until stable.

        stable = False
        while not stable:
            stable = True
            for uid, target in intentions.items():
                if uid in bounced_units: continue

                # Check target availability
                # If target is currently occupied...
                occupiers = unit_positions.get(target, [])

                # Logic: If stack is full, or occupied by enemy (blocked), or friend bounced
                # Simplified: Blocked if occupied by ANY unit that is staying there.

                blocked = False
                for occ in occupiers:
                    # Case 1: Occupier is Enemy (Block)
                    if occ.owner != units_by_id[uid].owner:
                        blocked = True

                    # Case 2: Occupier is Friendly, but NOT moving (Stationary)
                    elif occ.id not in intentions:
                        # Check stack limit (10)
                        if len(occupiers) >= 10: blocked = True

                    # Case 3: Occupier intended to move, but BOUNCED
                    elif occ.id in intentions and occ.id in bounced_units:
                        if len(occupiers) >= 10: blocked = True

                if blocked:
                    bounced_units.add(uid)
                    stable = False

        # --- Execution ---
        for uid, target in intentions.items():
            if uid not in bounced_units:
                unit = units_by_id[uid]
                # Update coords
                unit.q = target.q
                unit.r = target.r
                # Consume Fuel/MP (Stub)
                unit.mp -= 1

    # --- 2.5 Combat Logic ---

    def _resolve_combat(self, state: GameState, unit_positions: Dict[Hex, List[UnitState]]):
        """
        Simultaneous Combat Resolution.
        Calculates damage for ALL hexes before applying it.
        """

        # Map: UnitID -> Damage Received
        pending_damage = defaultdict(float)

        # Identify all populated hexes
        active_hexes = [h for h, units in unit_positions.items() if units]

        for hex_loc in active_hexes:
            defenders = unit_positions[hex_loc]
            if not defenders: continue

            owner_def = defenders[0].owner

            # Check all 6 neighbors for enemies
            neighbors = hex_neighbors(hex_loc)
            total_incoming_raw = 0.0

            # 1. Calculate Raw Output (O_raw) from Enemies
            for n_hex in neighbors:
                attackers = unit_positions.get(n_hex, [])
                # Filter for enemies
                enemy_attackers = [u for u in attackers if u.owner != owner_def]

                for atk in enemy_attackers:
                    # Formula: ATK * (CurrentHP / MaxHP)
                    # Terrain Mod would go here
                    efficiency = atk.hp / self._get_max_hp(atk.type)
                    raw_dmg = self._get_base_atk(atk.type) * efficiency
                    total_incoming_raw += raw_dmg

            if total_incoming_raw <= 0:
                continue

            # 2. Distribute Damage (Focus Fire on Weakest)
            # Sort defenders by Absolute HP (ascending)
            defenders.sort(key=lambda u: u.hp)

            remaining_dmg = total_incoming_raw

            # Calculate Mitigation for the stack (assuming hex terrain shared)
            # For simplicity, using Plains (0) or lookup from map
            terrain_def = 0 # Stub: Needs map lookup

            for unit in defenders:
                if remaining_dmg <= 0: break

                # M = TotalDef / (TotalDef + 25)
                base_def = self._get_base_def(unit.type)
                total_def = base_def + terrain_def
                mitigation = total_def / (total_def + DEF_CONSTANT)

                # E_hp = CurrentHP / (1 - M)
                curr_hp = unit.hp
                e_hp = curr_hp / (1.0 - mitigation)

                if remaining_dmg >= e_hp:
                    # Unit Dies
                    remaining_dmg -= e_hp
                    pending_damage[unit.id] = unit.hp # Kill it

                    # Record Event
                    state.events.append(Event(
                        type="COMBAT",
                        loc=HexCoord(q=hex_loc.q, r=hex_loc.r),
                        details=CombatDetails(
                            attacker="Enemies", defender=unit.owner,
                            damage_in=e_hp, casualties=[unit.id]
                        )
                    ))
                else:
                    # Unit Survives, apply real damage
                    # RealDmg = O_raw * (1 - M)
                    real_dmg = remaining_dmg * (1.0 - mitigation)
                    pending_damage[unit.id] = real_dmg
                    remaining_dmg = 0

        # 3. Apply Damage & Prune Dead
        alive_units = []
        for unit in state.you.units:
            if unit.id in pending_damage:
                unit.hp -= pending_damage[unit.id]

            if unit.hp > 0.5: # Epsilon for float
                alive_units.append(unit)
            else:
                pass # Unit removed

        state.you.units = alive_units

    # --- Helpers ---

    def _get_max_hp(self, u_type: UnitType) -> int:
        stats = {
            UnitType.CHIEF: 150, UnitType.ARMORED: 120,
            UnitType.SCOUT: 40, UnitType.LIGHT_INFANTRY: 60
        }
        return stats.get(u_type, 60)

    def _get_base_atk(self, u_type: UnitType) -> int:
        stats = {
            UnitType.CHIEF: 12, UnitType.ARMORED: 20,
            UnitType.SCOUT: 6, UnitType.LIGHT_INFANTRY: 10
        }
        return stats.get(u_type, 10)

    def _get_base_def(self, u_type: UnitType) -> int:
        stats = {
            UnitType.CHIEF: 12, UnitType.ARMORED: 16,
            UnitType.SCOUT: 4, UnitType.LIGHT_INFANTRY: 6
        }
        return stats.get(u_type, 6)
