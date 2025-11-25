from pydantic import BaseModel
from typing import List, Literal, Optional

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
