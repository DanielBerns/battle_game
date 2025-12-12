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
        units_by_id = {u.id: u for u in next_state.you.units}
        unit_positions = defaultdict(list)
        for u in next_state.you.units:
            unit_positions[Hex(u.q, u.r)].append(u)

        # 2. Validate & Filter Orders
        move_orders = [o for o in orders if o.type == OrderType.MOVE and o.id in units_by_id]

        # --- NEW: Process Research Orders ---
        research_orders = [o for o in orders if o.type == OrderType.RESEARCH]
        for order in research_orders:
            # Check if we have resources (MVP: Global check)
            cost = 200
            if next_state.you.resources.I >= cost:
                if order.tech_id not in next_state.you.unlocked_upgrades:
                    next_state.you.resources.I -= cost
                    next_state.you.unlocked_upgrades.append(order.tech_id)
                    next_state.events.append(Event(
                        type="RESEARCH",
                        loc=HexCoord(q=0, r=0),
                        details={"tech_id": order.tech_id}
                    ))
            else:
                 pass # Not enough resources

        # 3. Movement Resolution ("Lock & Bounce")
        self._resolve_movement(next_state, move_orders, units_by_id, unit_positions)

        # 4. Combat Resolution ("EHP Model")
        self._resolve_combat(next_state, unit_positions)

        # 5. Victory Check (Win/Draw Conditions)
        self._check_victory(next_state)

        return next_state

    def _check_victory(self, state: GameState):
        """
        Checks for elimination conditions and updates GameStatus if the match is over.
        """
        active_chiefs = set()

        for unit in state.you.units:
            if unit.type == UnitType.CHIEF:
                active_chiefs.add(unit.owner)

        if not active_chiefs:
            state.game_status = GameStatus.FINISHED
            state.events.append(Event(
                type="ELIMINATION",
                loc=HexCoord(q=0, r=0),
                details={"result": "DRAW", "reason": "Mutual Annihilation"}
            ))
            return

        if len(active_chiefs) == 1:
            winner = list(active_chiefs)[0]
            state.game_status = GameStatus.FINISHED
            state.events.append(Event(
                type="ELIMINATION",
                loc=HexCoord(q=0, r=0),
                details={"result": "WIN", "winner": winner}
            ))

    # --- 2.4 Movement Logic ---

    def _resolve_movement(self, state: GameState, move_orders: List[Order],
                          units_by_id: Dict[str, UnitState],
                          unit_positions: Dict[Hex, List[UnitState]]):

        intentions: Dict[str, Hex] = {}
        origins: Dict[str, Hex] = {}

        for order in move_orders:
            unit = units_by_id[order.id]
            target = Hex(order.dest.q, order.dest.r)
            origin = Hex(unit.q, unit.r)

            intentions[unit.id] = target
            origins[unit.id] = origin

        targets_map = defaultdict(list)
        for uid, target in intentions.items():
            targets_map[target].append(uid)

        bounced_units = set()

        for target, uids in targets_map.items():
            if len(uids) > 1:
                uids.sort(key=lambda x: (units_by_id[x].mp * 1000) + abs(hash(x)), reverse=True)
                winner = uids[0]
                losers = uids[1:]
                for l in losers:
                    bounced_units.add(l)

        for uid, target in intentions.items():
            if uid in bounced_units: continue
            occupiers = unit_positions.get(target, [])
            for occ in occupiers:
                if occ.id in intentions and intentions[occ.id] == origins[uid]:
                    if occ.owner != units_by_id[uid].owner:
                        bounced_units.add(uid)
                        bounced_units.add(occ.id)

        stable = False
        while not stable:
            stable = True
            for uid, target in intentions.items():
                if uid in bounced_units: continue
                occupiers = unit_positions.get(target, [])
                blocked = False
                for occ in occupiers:
                    if occ.owner != units_by_id[uid].owner:
                        blocked = True
                    elif occ.id not in intentions:
                        if len(occupiers) >= 10: blocked = True
                    elif occ.id in intentions and occ.id in bounced_units:
                        if len(occupiers) >= 10: blocked = True

                if blocked:
                    bounced_units.add(uid)
                    stable = False

        for uid, target in intentions.items():
            if uid not in bounced_units:
                unit = units_by_id[uid]
                unit.q = target.q
                unit.r = target.r
                unit.mp -= 1

    # --- 2.5 Combat Logic ---

    def _resolve_combat(self, state: GameState, unit_positions: Dict[Hex, List[UnitState]]):
        """
        Simultaneous Combat Resolution.
        Calculates damage for ALL hexes before applying it.
        """

        pending_damage = defaultdict(float)
        active_hexes = [h for h, units in unit_positions.items() if units]

        # Grab unlocked upgrades for stats calculation
        upgrades = state.you.unlocked_upgrades

        for hex_loc in active_hexes:
            defenders = unit_positions[hex_loc]
            if not defenders: continue

            owner_def = defenders[0].owner
            neighbors = hex_neighbors(hex_loc)
            total_incoming_raw = 0.0

            for n_hex in neighbors:
                attackers = unit_positions.get(n_hex, [])
                enemy_attackers = [u for u in attackers if u.owner != owner_def]

                for atk in enemy_attackers:
                    efficiency = atk.hp / self._get_max_hp(atk.type)
                    # Pass upgrades here
                    raw_dmg = self._get_base_atk(atk.type, upgrades) * efficiency
                    total_incoming_raw += raw_dmg

            if total_incoming_raw <= 0:
                continue

            defenders.sort(key=lambda u: u.hp)
            remaining_dmg = total_incoming_raw
            terrain_def = 0

            for unit in defenders:
                if remaining_dmg <= 0: break

                # Pass upgrades here
                base_def = self._get_base_def(unit.type, upgrades)
                total_def = base_def + terrain_def
                mitigation = total_def / (total_def + DEF_CONSTANT)

                curr_hp = unit.hp
                e_hp = curr_hp / (1.0 - mitigation)

                if remaining_dmg >= e_hp:
                    remaining_dmg -= e_hp
                    pending_damage[unit.id] = unit.hp
                    state.events.append(Event(
                        type="COMBAT",
                        loc=HexCoord(q=hex_loc.q, r=hex_loc.r),
                        details=CombatDetails(
                            attacker="Enemies", defender=unit.owner,
                            damage_in=e_hp, casualties=[unit.id]
                        )
                    ))
                else:
                    real_dmg = remaining_dmg * (1.0 - mitigation)
                    pending_damage[unit.id] = real_dmg
                    remaining_dmg = 0

        alive_units = []
        for unit in state.you.units:
            if unit.id in pending_damage:
                unit.hp -= pending_damage[unit.id]

            if unit.hp > 0.5:
                alive_units.append(unit)
            else:
                pass

        state.you.units = alive_units

    # --- Helpers ---

    def _get_max_hp(self, u_type: UnitType) -> int:
        stats = {
            UnitType.CHIEF: 150, UnitType.ARMORED: 120,
            UnitType.SCOUT: 40, UnitType.LIGHT_INFANTRY: 60
        }
        return stats.get(u_type, 60)

    def _get_base_atk(self, u_type: UnitType, upgrades: List[str] = []) -> float:
        stats = {
            UnitType.CHIEF: 12, UnitType.ARMORED: 20,
            UnitType.SCOUT: 6, UnitType.LIGHT_INFANTRY: 10
        }
        val = stats.get(u_type, 10)

        # --- Upgrade Logic ---
        if u_type == UnitType.LIGHT_INFANTRY and "INFANTRY_TIER_1" in upgrades:
            return val * 1.10

        return float(val)

    def _get_base_def(self, u_type: UnitType, upgrades: List[str] = []) -> float:
        stats = {
            UnitType.CHIEF: 12, UnitType.ARMORED: 16,
            UnitType.SCOUT: 4, UnitType.LIGHT_INFANTRY: 6
        }
        val = stats.get(u_type, 6)

        # --- Upgrade Logic ---
        if u_type == UnitType.LIGHT_INFANTRY and "INFANTRY_TIER_1" in upgrades:
            return val * 1.10

        return float(val)
