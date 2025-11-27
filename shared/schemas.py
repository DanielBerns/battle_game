from enum import Enum
from typing import List, Optional, Dict, Literal, Union
from pydantic import BaseModel, Field, field_validator

class HexCoord(BaseModel):
    q: int
    r: int

    def __hash__(self):
        return hash((self.q, self.r))

class UnitState(BaseModel):
    id: str
    owner_id: str
    type: str # "Armored", "Scout", etc.
    hp: float
    mp: int
    coords: HexCoord

class GameState(BaseModel):
    tick: int
    units: List[UnitState]
    map_bounds: tuple[int, int]
    # ... resources, facilities ...

class Order(BaseModel):
    type: Literal["MOVE", "BUILD"]
    unit_id: Optional[str] = None
    fac_id: Optional[str] = None
    dest: Optional[HexCoord] = None
    build_type: Optional[str] = None


# --- Enums (Strict Vocabulary) ---

class TerrainType(str, Enum):
    PLAINS = "Plains"
    HILLS = "Hills"
    FOREST = "Forest"
    CITY = "City"
    MOUNTAIN = "Mountain"
    WATER = "Water"

class UnitType(str, Enum):
    CHIEF = "Chief"
    LIGHT_INFANTRY = "Light Infantry"
    SCOUT = "Scout"
    ARMORED = "Armored"
    MECHANIZED = "Mechanized"
    SPECIAL_FORCES = "Special Forces"

class GameStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"

class OrderType(str, Enum):
    MOVE = "MOVE"
    BUILD = "BUILD"

# --- Basic Primitives ---

class HexCoord(BaseModel):
    """
    Data Transfer Object for Hex coordinates.
    Maps to {"q": int, "r": int} JSON.
    """
    q: int
    r: int

    def __hash__(self):
        return hash((self.q, self.r))

    def __eq__(self, other):
        return self.q == other.q and self.r == other.r

class Resources(BaseModel):
    M: int = 0 # Materials
    F: int = 0 # Fuel
    I: int = 0 # Intel

# --- 3.1 Initialization (match_start) ---

class StaticTerrain(BaseModel):
    q: int
    r: int
    type: TerrainType

class MapData(BaseModel):
    width: int
    height: int
    static_terrain: List[StaticTerrain]

class GameConstants(BaseModel):
    def_constant: int = 25
    max_rounds: int = 3
    # Add other balancing constants here if needed

class MatchStart(BaseModel):
    """
    Sent once at the start of the game.
    See Spec Section 3.1
    """
    match_id: str
    map: MapData
    my_id: str
    constants: GameConstants

# --- 3.2 Game Loop (state_tick) ---

class UnitState(BaseModel):
    id: str
    type: UnitType
    q: int
    r: int
    hp: float
    mp: int # Current Movement Points
    owner: Optional[str] = None # Optional because 'you' list implies owner, enemies need it explicit

class FacilityState(BaseModel):
    id: str
    q: int
    r: int
    owner: Optional[str] = None
    queue: List[str] = [] # List of UnitTypes being built

class ControlUpdate(BaseModel):
    q: int
    r: int
    owner: str

class CombatDetails(BaseModel):
    attacker: str
    defender: str
    damage_in: float
    casualties: List[str]

class Event(BaseModel):
    type: Literal["COMBAT", "CAPTURE", "ELIMINATION"]
    loc: HexCoord
    details: Union[CombatDetails, Dict]

class VisibleChanges(BaseModel):
    units: List[UnitState] # Enemies seen this tick
    control_updates: List[ControlUpdate] # Hexes that changed hands

class PlayerState(BaseModel):
    resources: Resources
    units: List[UnitState]
    facilities: List[FacilityState]

class GameState(BaseModel):
    """
    Sent every tick. Contains dynamic data.
    See Spec Section 3.2
    """
    tick: int
    game_status: GameStatus
    you: PlayerState
    visible_changes: VisibleChanges
    events: List[Event]

# --- 3.3 Orders (submit_orders) ---

class Order(BaseModel):
    type: OrderType

    # MOVE specific
    id: Optional[str] = None # Unit ID
    dest: Optional[HexCoord] = None

    # BUILD specific
    fac_id: Optional[str] = None
    unit: Optional[UnitType] = None

    @field_validator('dest')
    def validate_move(cls, v, values):
        if values.data.get('type') == OrderType.MOVE and v is None:
            raise ValueError('MOVE order requires a destination (dest)')
        return v

    @field_validator('unit')
    def validate_build(cls, v, values):
        if values.data.get('type') == OrderType.BUILD and v is None:
            raise ValueError('BUILD order requires a unit type')
        return v

class OrderSubmission(BaseModel):
    """
    The payload sent by the client every tick.
    See Spec Section 3.3
    """
    tick: int # Must match Server Tick + 1
    orders: List[Order]

    @field_validator('orders')
    def check_limit(cls, v):
        if len(v) > 50:
            raise ValueError('Rate Limit Exceeded: Max 50 orders per tick.')
        return v
