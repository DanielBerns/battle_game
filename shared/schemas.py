import uuid
from enum import Enum
from typing import List, Optional, Dict, Literal, Union
from pydantic import BaseModel, Field, field_validator

# --- Enums ---

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
    WAITING = "WAITING"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"

class OrderType(str, Enum):
    MOVE = "MOVE"
    BUILD = "BUILD"
    RESEARCH = "RESEARCH"

# --- Basic Primitives ---

class HexCoord(BaseModel):
    q: int
    r: int

    def __hash__(self):
        return hash((self.q, self.r))

    def __eq__(self, other):
        return self.q == other.q and self.r == other.r

class Resources(BaseModel):
    M: int = 0
    F: int = 0
    I: int = 0

# --- API Payloads ---

class GameInitRequest(BaseModel):
    match_id: str
    initial_resources: Resources

# --- Initialization ---

class StaticTerrain(BaseModel):
    q: int
    r: int
    type: TerrainType

class MapData(BaseModel):
    width: int
    height: int
    radius: Optional[int] = None  # <--- NEW FIELD
    static_terrain: List[StaticTerrain]

class GameConstants(BaseModel):
    def_constant: int = 25
    max_rounds: int = 3

class MatchStart(BaseModel):
    match_id: str
    my_id: str
    map: MapData
    constants: GameConstants

# --- State ---

class UnitState(BaseModel):
    id: str
    type: UnitType
    q: int
    r: int
    hp: float
    mp: int
    owner: Optional[str] = None

class FacilityState(BaseModel):
    id: str
    q: int
    r: int
    owner: Optional[str] = None
    queue: List[str] = []

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
    type: Literal["COMBAT", "CAPTURE", "ELIMINATION", "RESEARCH", "BUILD"]
    loc: HexCoord
    details: Union[CombatDetails, Dict]

class VisibleChanges(BaseModel):
    units: List[UnitState]
    control_updates: List[ControlUpdate]

class PlayerState(BaseModel):
    resources: Resources
    units: List[UnitState]
    facilities: List[FacilityState]
    unlocked_upgrades: List[str] = []

class GameState(BaseModel):
    tick: int
    game_status: GameStatus
    you: PlayerState
    visible_changes: VisibleChanges
    events: List[Event]

# --- Orders ---

class Order(BaseModel):
    type: OrderType

    # MOVE
    id: Optional[str] = None
    dest: Optional[HexCoord] = None

    # BUILD
    fac_id: Optional[str] = None
    unit: Optional[UnitType] = None

    # RESEARCH
    tech_id: Optional[str] = None

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

    @field_validator('tech_id')
    def validate_research(cls, v, values):
        if values.data.get('type') == OrderType.RESEARCH and v is None:
            raise ValueError('RESEARCH order requires a tech_id')
        return v

class OrderSubmission(BaseModel):
    tick: int
    orders: List[Order]

    @field_validator('orders')
    def check_limit(cls, v):
        if len(v) > 50:
            raise ValueError('Rate Limit Exceeded: Max 50 orders per tick.')
        return v
