import math
import uuid
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict
from copy import deepcopy

from shared.schemas import (
    GameState, UnitState, Order, OrderType, HexCoord,
    GameStatus, Event, CombatDetails, UnitType, Resources,
    FacilityState, PlayerState, VisibleChanges
)
from shared.hex_math import Hex, hex_neighbors, hex_distance # Ensure hex_distance is imported

# --- Constants ---
DEF_CONSTANT = 25
UNIT_COSTS = {
    UnitType.LIGHT_INFANTRY: {"M": 40, "F": 0, "I": 0},
    UnitType.SCOUT: {"M": 60, "F": 0, "I": 0},
    UnitType.ARMORED: {"M": 120, "F": 40, "I": 0},
    UnitType.MECHANIZED: {"M": 140, "F": 60, "I": 0},
    UnitType.SPECIAL_FORCES: {"M": 80, "F": 0, "I": 30},
}

# Upkeep per 10 ticks
UNIT_UPKEEP = {
    UnitType.ARMORED: 4,
    UnitType.MECHANIZED: 6
}
RESEARCH_COST = 200

class GameEngine:
    def __init__(self, match_id: str, map_radius: int = 20):
        self.match_id = match_id
        self.map_radius = map_radius # <--- Store radius
        # State container
        self.current_state: Optional[GameState] = None
        # Authoritative Resource Store: { "p_red": Resources(...), "p_blue": ... }
        self.player_resources: Dict[str, Resources] = {}
        # Authoritative Upgrades Store: { "p_red": ["TECH_1"], ... }
        self.player_upgrades: Dict[str, List[str]] = defaultdict(list)

    def initialize_dynamic(self, resources: Resources):
        """Initializes a new game state with provided resources."""
        # 1. Setup Initial Units & Facilities
        units = [
            UnitState(id="u_red_1", type=UnitType.CHIEF, q=-3, r=-3, hp=150, mp=1, owner="p_red"),
            UnitState(id="u_blue_1", type=UnitType.CHIEF, q=3, r=3, hp=150, mp=1, owner="p_blue")
        ]
        facilities = [
            FacilityState(id="f_red_1", q=-3, r=-3, owner="p_red"),
            FacilityState(id="f_blue_1", q=3, r=3, owner="p_blue")
        ]

        # 2. Init Stores
        self.player_resources = {
            "p_red": deepcopy(resources),
            "p_blue": deepcopy(resources)
        }
        self.player_upgrades = defaultdict(list)

        # 3. Create Initial State
        self.current_state = GameState(
            tick=0,
            game_status=GameStatus.ACTIVE,
            you=PlayerState(
                resources=Resources(), # Placeholder, main.py injects correct view
                units=units,
                facilities=facilities,
                unlocked_upgrades=[]
            ),
            visible_changes=VisibleChanges(units=[], control_updates=[]),
            events=[]
        )

    def process_tick(self, state: GameState, orders: List[Tuple[str, Order]]) -> GameState:
        """
        Main Simulation Step.
        Args:
            state: Current GameState snapshot
            orders: List of (player_id, Order) tuples
        """
        next_state = deepcopy(state)
        next_state.tick += 1
        next_state.events = []

        # 0. Refuel & Upkeep (Fixing stuck units)
        self._reset_mp_and_upkeep(next_state)

        # 1. Indexing
        units_by_id = {u.id: u for u in next_state.you.units}
        unit_positions = defaultdict(list)
        for u in next_state.you.units:
            unit_positions[Hex(u.q, u.r)].append(u)

        facilities_by_id = {f.id: f for f in next_state.you.facilities}

        # 2. Process Orders

        # --- RESEARCH --- (NEW)
        for player_id, order in orders:
            if order.type == OrderType.RESEARCH:
                self._handle_research(player_id, order, next_state)

        # --- BUILD ---
        # Strategy: Process builds first so units can't move same turn (unless we change logic)
        for player_id, order in orders:
            if order.type == OrderType.BUILD:
                self._handle_build(player_id, order, next_state, unit_positions, facilities_by_id)

        # --- RESEARCH ---
        for player_id, order in orders:
            if order.type == OrderType.RESEARCH:
                self._handle_research(player_id, order, next_state)

        # --- MOVE ---
        # Filter only valid move orders
        move_orders = []
        for player_id, order in orders:
            if order.type == OrderType.MOVE and order.id in units_by_id:
                # Security check: Ensure player owns the unit
                if units_by_id[order.id].owner == player_id:
                    move_orders.append(order)

        self._resolve_movement(next_state, move_orders, units_by_id, unit_positions)

        # 3. Combat
        self._resolve_combat(next_state, unit_positions)

        # 4. Victory Check
        self._check_victory(next_state)

        return next_state

    # --- New / Updated Logic ---

    def _reset_mp_and_upkeep(self, state: GameState):
        """Resets MP for all units and handles Fuel upkeep every 10 ticks."""
        is_upkeep_tick = (state.tick % 10 == 0)

        for unit in state.you.units:
            # 1. Determine Max MP
            stats = self._get_unit_stats(unit.type)
            max_mp = stats["mp"]

            # 2. Handle Upkeep (Fuel Consumption)
            if is_upkeep_tick and unit.type in UNIT_UPKEEP:
                cost = UNIT_UPKEEP[unit.type]
                owner_res = self.player_resources.get(unit.owner)

                if owner_res and owner_res.F >= cost:
                    owner_res.F -= cost
                    # Full Refuel
                    unit.mp = max_mp
                else:
                    # Starvation Penalty (-25% Speed -> simplified to 0 or reduced MP)
                    # For MVP, let's set MP to 0 or 1 to show impact
                    unit.mp = max(0, int(max_mp * 0.75))
            else:
                # Normal Tick: Reset MP
                unit.mp = max_mp

    def _handle_research(self, player_id: str, order: Order, state: GameState):
        """Handle Instant Research."""
        res = self.player_resources.get(player_id, Resources())
        upgrades = self.player_upgrades[player_id]

        if order.tech_id in upgrades: return

        if res.I >= RESEARCH_COST:
            res.I -= RESEARCH_COST
            upgrades.append(order.tech_id)
            # Update state for client view
            if state.you.resources: # Just in case
                 pass # Resources in state are merely a view, real data is in self.player_resources

            state.events.append(Event(
                type="RESEARCH", loc=HexCoord(q=0, r=0),
                details={"tech_id": order.tech_id, "owner": player_id}
            ))

    # --- Order Handlers ---

    def _handle_build(self, player_id: str, order: Order, state: GameState,
                      unit_positions: Dict[Hex, List[UnitState]],
                      facilities_by_id: Dict[str, FacilityState]):

        if order.fac_id not in facilities_by_id: return
        fac = facilities_by_id[order.fac_id]

        # Validation: Ownership & Cap
        if fac.owner != player_id: return

        loc = Hex(fac.q, fac.r)
        if len(unit_positions[loc]) >= 10: return # Stack full

        # Validation: Resources
        costs = UNIT_COSTS.get(order.unit, {})
        res = self.player_resources.get(player_id, Resources())

        if (res.M >= costs.get("M", 0) and
            res.F >= costs.get("F", 0) and
            res.I >= costs.get("I", 0)):

            # Deduct
            res.M -= costs.get("M", 0)
            res.F -= costs.get("F", 0)
            res.I -= costs.get("I", 0)

            # Spawn Unit
            u_id = f"u_{uuid.uuid4().hex[:6]}"
            stats = self._get_unit_stats(order.unit)

            new_unit = UnitState(
                id=u_id, type=order.unit,
                q=fac.q, r=fac.r,
                hp=stats["hp"], mp=stats["mp"],
                owner=player_id
            )

            state.you.units.append(new_unit)
            unit_positions[loc].append(new_unit)

            state.events.append(Event(
                type="BUILD", loc=HexCoord(q=fac.q, r=fac.r),
                details={"unit": order.unit, "owner": player_id}
            ))

    # --- Movement & Combat ---

    def _resolve_movement(self, state: GameState, move_orders: List[Order],
                          units_by_id: Dict[str, UnitState],
                          unit_positions: Dict[Hex, List[UnitState]]):
        intentions: Dict[str, Hex] = {}
        origins: Dict[str, Hex] = {}
        center_hex = Hex(0, 0) # <--- Center of world

        for order in move_orders:
            unit = units_by_id[order.id]
            # Simple Range Check (1 hex)
            target = Hex(order.dest.q, order.dest.r)
            origin = Hex(unit.q, unit.r)

            # --- MAP BOUNDARY CHECK (NEW) ---
            if hex_distance(center_hex, target) > self.map_radius:
                # Invalid move (Out of Bounds)
                continue

            # If distance > unit.mp, invalid (Basic check)
            # In full impl, use pathfinding. Here assume adjacency for 1 MP
            intentions[unit.id] = target
            origins[unit.id] = origin

        targets_map = defaultdict(list)
        for uid, target in intentions.items():
            targets_map[target].append(uid)

        bounced_units = set()

        # Phase A: Conflict (Same target)
        for target, uids in targets_map.items():
            if len(uids) > 1:
                uids.sort(key=lambda x: (units_by_id[x].mp * 1000) + abs(hash(x)), reverse=True)
                winner = uids[0]
                losers = uids[1:]
                for l in losers:
                    bounced_units.add(l)

        # Phase B: Collision (Head to head)
        for uid, target in intentions.items():
            if uid in bounced_units: continue
            occupiers = unit_positions.get(target, [])
            for occ in occupiers:
                if occ.id in intentions and intentions[occ.id] == origins[uid]:
                    if occ.owner != units_by_id[uid].owner:
                        bounced_units.add(uid)
                        bounced_units.add(occ.id)

        # Phase C: Dependency (Chain)
        stable = False
        while not stable:
            stable = True
            for uid, target in intentions.items():
                if uid in bounced_units: continue
                occupiers = unit_positions.get(target, [])
                blocked = False
                for occ in occupiers:
                    # Enemy blocks
                    if occ.owner != units_by_id[uid].owner:
                        blocked = True
                    # Friend blocks if not moving or bounced
                    elif occ.id not in intentions:
                        if len(occupiers) >= 10: blocked = True
                    elif occ.id in intentions and occ.id in bounced_units:
                        if len(occupiers) >= 10: blocked = True

                if blocked:
                    bounced_units.add(uid)
                    stable = False

        # Execute
        for uid, target in intentions.items():
            if uid not in bounced_units:
                unit = units_by_id[uid]
                unit.q = target.q
                unit.r = target.r
                unit.mp = max(0, unit.mp - 1)

    def _resolve_combat(self, state: GameState, unit_positions: Dict[Hex, List[UnitState]]):
        pending_damage = defaultdict(float)
        active_hexes = [h for h, units in unit_positions.items() if units]

        for hex_loc in active_hexes:
            defenders = unit_positions[hex_loc]
            if not defenders: continue
            owner_def = defenders[0].owner

            # Get Defenders' upgrades
            def_upgrades = self.player_upgrades.get(owner_def, [])

            total_incoming_raw = 0.0
            neighbors = hex_neighbors(hex_loc)

            # Calculate Incoming Damage
            for n_hex in neighbors:
                attackers = unit_positions.get(n_hex, [])
                enemy_attackers = [u for u in attackers if u.owner != owner_def]

                for atk in enemy_attackers:
                    # Get Attacker's upgrades
                    atk_upgrades = self.player_upgrades.get(atk.owner, [])

                    efficiency = atk.hp / self._get_max_hp(atk.type)
                    base_atk = self._get_base_atk(atk.type, atk_upgrades)
                    raw_dmg = base_atk * efficiency
                    total_incoming_raw += raw_dmg

            if total_incoming_raw <= 0: continue

            # Distribute Damage
            defenders.sort(key=lambda u: u.hp)
            remaining_dmg = total_incoming_raw
            terrain_def = 0 # Placeholder for map lookup

            for unit in defenders:
                if remaining_dmg <= 0: break

                base_def = self._get_base_def(unit.type, def_upgrades)
                total_def = base_def + terrain_def
                mitigation = total_def / (total_def + DEF_CONSTANT)

                curr_hp = unit.hp
                e_hp = curr_hp / (1.0 - mitigation)

                if remaining_dmg >= e_hp:
                    remaining_dmg -= e_hp
                    pending_damage[unit.id] = unit.hp
                    state.events.append(Event(
                        type="COMBAT", loc=HexCoord(q=hex_loc.q, r=hex_loc.r),
                        details=CombatDetails(attacker="Enemies", defender=unit.owner, damage_in=e_hp, casualties=[unit.id])
                    ))
                else:
                    real_dmg = remaining_dmg * (1.0 - mitigation)
                    pending_damage[unit.id] = real_dmg
                    remaining_dmg = 0

        # Apply Damage
        alive_units = []
        for unit in state.you.units:
            if unit.id in pending_damage:
                unit.hp -= pending_damage[unit.id]
            if unit.hp > 0.5:
                alive_units.append(unit)

        state.you.units = alive_units

    def _check_victory(self, state: GameState):
        active_chiefs = set()
        for unit in state.you.units:
            if unit.type == UnitType.CHIEF:
                active_chiefs.add(unit.owner)

        if not active_chiefs:
            state.game_status = GameStatus.FINISHED
            state.events.append(Event(type="ELIMINATION", loc=HexCoord(q=0,r=0), details={"res": "DRAW"}))
        elif len(active_chiefs) == 1:
            winner = list(active_chiefs)[0]
            state.game_status = GameStatus.FINISHED
            state.events.append(Event(type="ELIMINATION", loc=HexCoord(q=0,r=0), details={"res": "WIN", "winner": winner}))

    # --- Stat Helpers ---

    def _get_unit_stats(self, u_type: UnitType) -> dict:
        # Initial spawn stats
        stats = {
            UnitType.CHIEF: {"hp": 150, "mp": 1},
            UnitType.ARMORED: {"hp": 120, "mp": 1},
            UnitType.SCOUT: {"hp": 40, "mp": 3},
            UnitType.LIGHT_INFANTRY: {"hp": 60, "mp": 2},
            UnitType.MECHANIZED: {"hp": 90, "mp": 2},
            UnitType.SPECIAL_FORCES: {"hp": 80, "mp": 2},
        }
        return stats.get(u_type, {"hp": 10, "mp": 1})

    def _get_max_hp(self, u_type: UnitType) -> float:
        return float(self._get_unit_stats(u_type)["hp"])

    def _get_base_atk(self, u_type: UnitType, upgrades: List[str]) -> float:
        # Base stats
        base = 10.0
        if u_type == UnitType.ARMORED: base = 20.0
        if u_type == UnitType.MECHANIZED: base = 18.0
        if u_type == UnitType.SPECIAL_FORCES: base = 14.0
        if u_type == UnitType.CHIEF: base = 12.0
        if u_type == UnitType.SCOUT: base = 6.0

        # Modifiers
        mult = 1.0
        if u_type == UnitType.LIGHT_INFANTRY and "INFANTRY_TIER_1" in upgrades:
            mult += 0.10

        return base * mult

    def _get_base_def(self, u_type: UnitType, upgrades: List[str]) -> float:
        base = 6.0
        if u_type == UnitType.ARMORED: base = 16.0
        if u_type == UnitType.MECHANIZED: base = 12.0
        if u_type == UnitType.SPECIAL_FORCES: base = 10.0
        if u_type == UnitType.CHIEF: base = 12.0
        if u_type == UnitType.SCOUT: base = 4.0

        mult = 1.0
        if u_type == UnitType.LIGHT_INFANTRY and "INFANTRY_TIER_1" in upgrades:
            mult += 0.10

        return base * mult
