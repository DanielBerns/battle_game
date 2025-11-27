"""
Hexagonal Grid Math Library
System: Axial (q, r) & Cube (x, y, z)
Constraint: Flat-topped hexes (implied by standard ASCII map layouts, though math works for pointy too)
"""

import math
from dataclasses import dataclass
from typing import List, Tuple, Set, Iterator

@dataclass(frozen=True, eq=True)
class Hex:
    """
    Immutable Hexagon coordinate in Axial format.
    Frozen allows this to be used as dictionary keys (critical for map storage).
    """
    q: int
    r: int

    @property
    def s(self) -> int:
        """Calculates the implicit third cube coordinate."""
        return -self.q - self.r

    def __add__(self, other: 'Hex') -> 'Hex':
        return Hex(self.q + other.q, self.r + other.r)

    def __sub__(self, other: 'Hex') -> 'Hex':
        return Hex(self.q - other.q, self.r - other.r)

    def __repr__(self):
        return f"Hex({self.q}, {self.r})"

# --- Constants ---

# The 6 neighbors of a hex (q, r)
# Direction 0 starts at East (assuming flat-topped) or South-East (pointy)
HEX_DIRECTIONS = [
    Hex(1, 0), Hex(1, -1), Hex(0, -1),
    Hex(-1, 0), Hex(-1, 1), Hex(0, 1)
]

# --- Core Math Functions ---

def hex_length(hex: Hex) -> int:
    """Calculates the distance from (0,0) to the hex."""
    return int((abs(hex.q) + abs(hex.r) + abs(hex.s)) / 2)

def hex_distance(a: Hex, b: Hex) -> int:
    """
    Calculates the Manhattan distance between two hexes.
    Formula: max(|dq|, |dr|, |ds|) or (|dq| + |dr| + |ds|) / 2
    """
    vec = a - b
    return hex_length(vec)

def hex_neighbors(hex: Hex) -> List[Hex]:
    """Returns the 6 adjacent hexes."""
    return [hex + d for d in HEX_DIRECTIONS]

# --- Line of Sight & Geometry (Vision) ---

def _lerp(a: float, b: float, t: float) -> float:
    """Linear Interpolation between a and b."""
    return a + (b - a) * t

def _cube_lerp(a: Hex, b: Hex, t: float) -> Tuple[float, float, float]:
    """Interpolates between two hexes in Cube space."""
    return (
        _lerp(a.q, b.q, t),
        _lerp(a.r, b.r, t),
        _lerp(a.s, b.s, t)
    )

def _cube_round(frac_q: float, frac_r: float, frac_s: float) -> Hex:
    """
    Rounds floating point cube coordinates to the nearest valid integer Hex.
    Maintains the constraint q + r + s = 0.
    """
    q = round(frac_q)
    r = round(frac_r)
    s = round(frac_s)

    q_diff = abs(q - frac_q)
    r_diff = abs(r - frac_r)
    s_diff = abs(s - frac_s)

    # Reset the component with the largest change to satisfy constraint
    if q_diff > r_diff and q_diff > s_diff:
        q = -r - s
    elif r_diff > s_diff:
        r = -q - s
    else:
        # s is implicit in the return Hex, but needed for logic above
        pass

    return Hex(int(q), int(r))

def hex_linedraw(start: Hex, end: Hex) -> List[Hex]:
    """
    Returns a list of Hexes forming a straight line between start and end.
    Used for Line of Sight checks (Vision).
    """
    N = hex_distance(start, end)
    if N == 0:
        return [start]

    results = []
    # Nudge end points slightly to avoid edge cases directly on lines
    # (epsilon offset concept usually handled by the rounding logic,
    # but basic LERP works for standard grids)
    for i in range(N + 1):
        t = i / N
        fq, fr, fs = _cube_lerp(start, end, t)
        results.append(_cube_round(fq, fr, fs))

    return results

# --- Range & Area ---

def hex_spiral(center: Hex, radius: int) -> Iterator[Hex]:
    """
    Yields all hexes within a certain radius of the center (filled circle).
    Useful for 'Area of Effect' or Movement Range lookups.
    """
    for q in range(-radius, radius + 1):
        # r loop bounds depend on q to maintain hex shape
        r1 = max(-radius, -q - radius)
        r2 = min(radius, -q + radius)
        for r in range(r1, r2 + 1):
            yield center + Hex(q, r)

def hex_ring(center: Hex, radius: int) -> Iterator[Hex]:
    """Yields only the hexes at exactly distance == radius."""
    if radius == 0:
        yield center
        return

    # Start at one corner and walk around
    current = center + (HEX_DIRECTIONS[4] * radius) # Start at specific corner
    for i in range(6):
        for _ in range(radius):
            yield current
            current = current + HEX_DIRECTIONS[i]
