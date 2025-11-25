# Battle Game Specification v2.0 ⚔️

**Version:** 2.0 (Updated Movement & Combat Logic)
**Focus:** Deterministic Simulation, Competitive Balance, Bot API Efficiency.

-----

## 1\. Vision & Core Loop

  * **Vision:** A deterministic, hex-based strategy game where scripting optimization wins over twitch reflexes.
  * **Core Loop:**
    1.  **Macro:** Expand territory to secure Materials (M) and Fuel (F).
    2.  **Tech:** Secure Intel (I) nodes to unlock upgrades (Future).
    3.  **Micro:** Script coordinated movements to flank enemies and "Checkmate" their Chief.

-----

## 2\. Game Rules & Mechanics

### 2.1 Map & Hex System

  * **Grid:** Axial coordinates (q, r). Finite bounds (no wrapping).
  * **Terrain & Effects:**
      * **Plains:** Move Cost 1.
      * **Hills:** Move Cost 2, **+10 DEF**.
      * **Forest:** Move Cost 2, **+20 DEF**, -1 Vision (except Scouts).
      * **City/Facility:** Move Cost 1, Production capability.
      * **Impassable:** Mountains/Water (Cannot enter).
  * **Frontiers:** A hex is "Controlled" if occupied by a unit at the end of a turn. Facilities require 2 uncontested turns to flip ownership.

### 2.2 Economy (M/F/I)

  * **Materials (M):** Standard build cost.
  * **Fuel (F):** Required for Armored/Mechanized construction and **Upkeep**.
  * **Intel (I):** Special Forces cost and Tech Upgrades.
  * **Upkeep:**
      * Heavy units (Armored/Mech) consume Fuel every 10 ticks.
      * **Starvation:** If Fuel is 0 and Upkeep fails, units gain "Starved" status (-25% Move Speed, -20% ATK).

### 2.3 Unit Roster (Rebalanced)

  * **Global Cap:** 10 units per hex.
  * **Chief (King):**
      * HP 150, ATK 12, DEF 12, MP 1.
      * **Passive Aura:** Friendly units within 2 hexes gain **+10% DEF**.
      * **Risk:** If killed or captured, player is eliminated.
  * **Light Infantry:**
      * HP 60, ATK 10, DEF 6, MP 2. Cost: 40M.
      * Cheap fodder.
  * **Scout:**
      * HP 40, ATK 6, DEF 4, MP 3. Cost: **60M** (No Intel cost).
      * High vision, ignores Forest vision penalty.
  * **Armored (Tank):**
      * HP 120, ATK 20, DEF 16, MP 1. Cost: 120M / 40F.
      * Upkeep: 4F. High mitigation tank.
  * **Mechanized:**
      * HP 90, ATK 18, DEF 12, MP 2. Cost: 140M / 60F.
      * Upkeep: 6F. Fast striker.
  * **Special Forces:**
      * HP 80, ATK 14, DEF 10, MP 2. Cost: 80M / 30I.
      * Bonus: +10% ATK in enemy territory.

-----

### 2.4 Movement Resolution: "Lock & Bounce" ♟️

*Strict ordering to prevent non-deterministic race conditions.*

1.  **Intent Phase:** All players submit moves.
2.  **Resolution Phase:**
      * **A. Conflict (Same Target):** If multiple units target the *same empty hex*, the unit with the highest **Movement Initiative** succeeds. All others **Bounce** (stay in original hex).
          * *Initiative Score* = (Current MP \* 1000) + (Unit ID integer).
      * **B. Collision (Head-to-Head):** If Unit A moves to Hex Y, and Unit B (currently at Y) moves to Hex X (A's origin), and they are enemies:
          * Both units stop at the border.
          * **Immediate Combat** occurs between these specific units.
          * Movement is cancelled.
      * **C. Chain Dependency:** If Unit A moves to Hex Y (occupied by Friendly B), but Friendly B failed to move (due to Bounce or Collision), Unit A also Bounces.
3.  **Execution:** Valid moves are applied. Fuel is consumed.

-----

### 2.5 Combat Resolution: "Effective HP" Model 🛡️

*Combat occurs simultaneously. Damage is calculated based on Output vs. Mitigation.*

  * **Combat Loop:** Max 3 rounds per tick.
  * **Variables:**
      * `Defense_Constant (C)` = 25.
      * `Terrain_Bonus`: Adds flat value to Unit DEF.

**Step 1: Calculate Raw Output ($O_{raw}$)**
Sum of Attack from all units in the side, scaled by their health efficiency.
$$O_{raw} = \sum (\text{ATK} \times \frac{\text{CurrentHP}}{\text{MaxHP}}) \times \text{TerrainMod}_{\text{ATK}}$$

**Step 2: Distribute Damage (Focus Fire)**
Damage is applied to the enemy stack, targeting the unit with the **Lowest Absolute HP** first.

For each target unit:

1.  **Calculate Mitigation ($M$):**
    $$M = \frac{\text{DEF}_{\text{Total}}}{\text{DEF}_{\text{Total}} + 25}$$
    *(Example: 16 DEF + 4 Forest = 20. $20/45 = 44\%$ reduction).*
2.  **Calculate Effective HP ($E_{hp}$):**
    $$E_{hp} = \frac{\text{CurrentHP}}{1 - M}$$
3.  **Apply Damage:**
      * If $O_{raw} \ge E_{hp}$: Unit dies. Subtract $E_{hp}$ from $O_{raw}$. Continue to next weakest unit.
      * If $O_{raw} < E_{hp}$: Unit survives. Apply real damage: $O_{raw} \times (1-M)$. $O_{raw}$ becomes 0.

-----

### 2.6 Victory & "Checkmate" 👑

  * **Elimination:** A player is out if their Chief dies.
  * **Checkmate Rule (Capture):** A Chief is instantly captured (eliminated) if, at the end of the Movement Phase:
    1.  An enemy unit is in an adjacent hex.
    2.  The Chief has **0 Valid Exit Paths** (All adjacent hexes are either Terrain-Blocked, Occupied by Enemy, or covered by Enemy Zone of Control).
  * **Tie-Breaker:** If time expires, score = (Chief Alive \* 1000) + (Facilities \* 50) + (Unit Value).

-----

## 3\. Bot API & Schemas (JSON)

### 3.1 Initialization (`match_start`)

*Sent once at start. Contains static data to save bandwidth.*

```json
{
  "match_id": "m_12345",
  "map": {
    "width": 80,
    "height": 80,
    "static_terrain": [
      {"q": 0, "r": 0, "type": "Plains"},
      {"q": 0, "r": 1, "type": "Mountain"}
      // ... only sent once ...
    ]
  },
  "my_id": "p_red",
  "constants": { "def_constant": 25, "max_rounds": 3 }
}
```

### 3.2 Game Loop (`state_tick`)

*Sent every tick. Contains dynamic data only.*

```json
{
  "tick": 42,
  "game_status": "ACTIVE", // or "FINISHED"
  "you": {
    "resources": {"M": 200, "F": 50, "I": 0},
    "units": [
      {"id": "u1", "type": "Armored", "q": 10, "r": -5, "hp": 110, "mp": 1}
    ],
    "facilities": [{"id": "f1", "q": 10, "r": -5, "queue": []}]
  },
  "visible_changes": {
    "units": [
      {"id": "enemy_u5", "owner": "p_blue", "type": "Scout", "q": 11, "r": -5, "hp": 40}
    ],
    "control_updates": [{"q": 11, "r": -5, "owner": "p_blue"}]
  },
  "events": [
    {
      "type": "COMBAT",
      "loc": {"q": 10, "r": -5},
      "details": {
        "attacker": "p_blue",
        "defender": "p_red",
        "damage_in": 45.2,
        "casualties": ["u1_damaged"]
      }
    }
  ]
}
```

### 3.3 Orders (`submit_orders`)

```json
{
  "tick": 43, // Must match server tick + 1
  "orders": [
    {"type": "MOVE", "id": "u1", "dest": {"q": 11, "r": -5}},
    {"type": "BUILD", "fac_id": "f1", "unit": "Scout"}
  ]
}
```

-----

## 4\. Implementation Guidelines

### 4.1 Server Architecture

1.  **Input Buffer:** Collect orders until `Tick_Deadline` (e.g., T-100ms).
2.  **Simulation Step:**
      * Validate Orders (Ownership, Cost).
      * Run **Movement Resolution** (Bounce/Collision).
      * Run **Combat Resolution** (EHP Logic).
      * Run **Production/Resources** (Mines yield, queues tick down).
      * Update **Vision/Fog**.
3.  **Broadcast:** Serialize `state_tick` diffs to players.

### 4.2 Anti-Cheat & Constraints

  * **Fog of War:** Server strictly filters `visible_changes`. You never send data for units outside vision radius.
  * **Rate Limit:** Max 50 orders per tick per player.
  * **Determinism:** RNG (if used for damage variance 0.95-1.05) must be seeded by `hash(match_id + tick + hex_coord)`.

-----

## 5 Tech

1. The server side must be implemented in python, using fastapi, SQLAlchemy, pydantic, bcrypt, postgresql. 
2. The client side must be implemented in python, httpx, SQLAlchemy, pydantic, sqlite. 
3. The dashboard must be implemented with html, css, and node.js.
