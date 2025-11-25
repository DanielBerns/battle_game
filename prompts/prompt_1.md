
## 1) A new battle game ✅

- A multiplayer strategy game on a finite hex grid.
- Players control territories (contiguous zones), produce and manage varied warrior types, and aim to defeat opponents by capturing/eliminating their Chiefs warriors.
- Discrete time steps with simultaneous decisions.
- Real-time dashboard for monitoring battles and states.
- Players are scripted bots communicating with a central server.


## 2) Proposed Specification (MVP+) 🛠️

This spec aims for clarity, feasibility, and deterministic simulation suitable for AI scripting.

### 2.1 Vision and Core Loop
- Vision: Fast, tactical, deterministic hex-warfare with clear information constraints and meaningful territory control.
- Core Loop:
  1) Expand and secure resource nodes.
  2) Produce and upgrade units.
  3) Scout, plan, and execute coordinated offensives.
  4) Eliminate or capture enemy Chiefs units.

### 2.2 Game Settings
- Match types: 2–6 players.
- Time step: 1 server tick = 1 second (configurable: 1–60s).
- Match duration hard cap: 60 minutes (configurable: 60-3600m).
- Map sizes: Small (40x40 hexes), Medium (80x80), Large (160x160).

### 2.3 Map and Hex System
- Orientation: Pointy-top hexes.
- Coordinates: Axial (q, r). Distance: hex_distance = (|dq| + |dr| + |dq + dr|)/2.
- Terrain Types:
  - Plains: move cost 1.
  - Hills: move cost 2, +10% defense.
  - Forest: move cost 2, +20% defense, -1 vision for non-Scout.
  - City/Facility: move cost 1, production slots, capture points.
  - Impassable: cannot enter.
- World bounds: Finite, no wrap-around.
- Generation:
  - Symmetrical ring-based placement for spawns.
  - Resource nodes mirrored by sectors to ensure fairness.
- Frontier definition: Player frontier = controlled hexes adjacent to non-controlled hexes.

### 2.4 Territory and Control
- Control:
  - A hex is controlled by the last player to have an uncontested unit occupying it at end of tick.
  - Facilities/resources require 2 consecutive uncontested ticks to flip control.
- Disconnected zones remain controlled; supply penalties apply (see 2.7).

### 2.5 Resources and Economy
- Resource Types:
  - Materials (M): used for most unit/build costs.
  - Fuel (F): used for mechanized/armored movement and production.
  - Intel (I): used for upgrades and special abilities.
- Generation:
  - Resource Nodes on-map yield per tick when connected by supply to a controlled Facility.
  - Base Facility starts with 2 production slots; additional Facilities add +1 slot each.
- Storage cap: 5000 each (configurable); overflow lost.
- Upkeep:
  - Mechanized and Armored consume Fuel upkeep every 10 ticks; missing upkeep applies a -25% speed debuff.

### 2.6 Units (Warriors)
- Global rules:
  - Stack cap per hex: 10 total units; overflow attempts fail to enter.
  - Each unit has: HP, Attack, Defense, Move Points (MP/tick), Vision, Cost (M/F/I), Build Time (ticks).
  - No ranged combat in MVP (optional in future).
- Types:
  - Light Infantry:
    - HP 60, ATK 10, DEF 6, MP 2, Vision 2
    - Cost: 40M, Build: 3 ticks
    - Cheap backbone, no upkeep
  - Scout:
    - HP 40, ATK 6, DEF 4, MP 3, Vision 4 (ignores -1 forest penalty)
    - Cost: 50M 10I, Build: 3 ticks
    - Provides vision; lower combat value
  - Armored:
    - HP 120, ATK 20, DEF 16, MP 1, Vision 2
    - Cost: 120M 40F, Build: 6 ticks, Upkeep: 4F/10 ticks
    - High strength, slow
  - Mechanized:
    - HP 90, ATK 18, DEF 12, MP 2, Vision 2
    - Cost: 140M 60F, Build: 6 ticks, Upkeep: 6F/10 ticks
    - Versatile and strong
  - Special Forces:
    - HP 80, ATK 14, DEF 10, MP 2, Vision 3
    - Cost: 80M 30I, Build: 5 ticks
    - +10% attack when fighting in enemy-controlled hex
  - Chief:
    - HP 150, ATK 12, DEF 12, MP 1, Vision 2
    - Cost: free at start; unique; cannot be rebuilt
    - If killed: player eliminated
    - If captured (see 2.8): immediate elimination
- Upgrades (MVP Optional):
  - Tier 1 (cost 200I, 10 ticks): +10% ATK/DEF for one chosen class.
  - Tier 2 (cost 300I, 15 ticks): +1 MP for Scouts OR +10% DEF in Hills/Forest for Infantry classes.

### 2.7 Movement and Supply
- Movement:
  - MP spent per hex = terrain move cost; minimum 1.
  - Entering an enemy-occupied hex triggers combat (see 2.9).
  - Simultaneous movement into same empty hex: highest initiative wins (initiative = unit MP this tick + tie-break by lowest unit ID).
  - Zone of Control: Adjacent enemy units impose +1 move cost when entering/leaving their adjacent hexes (does not stack across multiple units).
- Supply:
  - A hex is “in supply” if connected via contiguous controlled hexes to any Facility.
  - Out-of-supply penalties: -1 MP (min 1), -20% ATK, cannot receive repairs/reinforcements.

### 3.8 Chief Rules and Victory Conditions
- Victory:
  - Eliminate all opposing Chiefs (via kill or capture).
  - Capture: Chief is captured if surrounded on all 6 adjacent hexes at end of tick by enemy-controlled hexes and at least one enemy unit is co-located; immediate elimination.
  - Simultaneous eliminations: If last two players eliminate each other’s Chiefs in same tick, match is a draw unless tie-breaker is enabled (see 2.13).

### 3.9 Combat Resolution
- Battle Grouping:
  - All units in a hex at end-of-movement phase are grouped by team; if opposing teams present, combat occurs.
- Round:
  - Each side’s effective strength S = sum over units: (ATK) * terrain_attack_modifier + adjacency_support
  - Defense pool D = sum over units: DEF * terrain_defense_modifier
  - Damage to side A = max(1, floor((S_B * R) - D_A_modifier))
  - R = random factor in [0.95, 1.05], seeded deterministically (see 2.12).
  - Damage distributed proportionally by unit max HP; excess rolls to next unit.
  - Combat repeats until one side has no units or max 3 rounds per tick (to limit time).
- Modifiers:
  - Hills +10% DEF; Forest +20% DEF (except Scouts ignore vision penalty only).
  - Flank bonus: if enemy-controlled hex is adjacent to 3+ hexes controlled by attacker, +10% ATK.
- Post-combat:
  - Surviving units that initiated entry occupy the hex if enemies are removed.
  - Chiefs cannot retreat automatically.

### 2.10 Production and Construction
- Facilities:
  - Each Facility has N production slots; Base starts with 2; captured Facilities add +1.
  - Queue per Facility; one unit per slot builds concurrently.
- Build rules:
  - Costs paid upfront; on insufficient storage, order rejected.
  - Build completes at end of tick when timer hits 0; unit spawns in the Facility hex (adheres to stack cap).
- Repairs:
  - Units auto-repair +5 HP per 5 ticks if in-supply and not engaged that tick.

### 2.11 Visibility and Fog of War
- Visibility radius = unit Vision; blocked only by Impassable terrain.
- Scouts ignore Forest vision penalty (others -1 in Forest).
- Players see:
  - All controlled hexes and any hex visible by any friendly unit.
  - Aggregates at frontiers in dashboard: friendlies by type count; enemies only if visible.
- Hidden info:
  - Enemy queues, resources, and unseen units are hidden.

### 2.12 Determinism, RNG, and Ticks
- Tick cadence: fixed server tick (default 1s).
- RNG:
  - Seeded per match: seed = hash(match_id).
  - Random draws per battle: hash(seed, tick, hex_q, hex_r, engagement_index).
- Order deadlines:
  - Orders must arrive at least 100 ms before tick boundary; late orders apply next tick.
- Order of operations each tick:
  1) Lock orders
  2) Validate/clip orders
  3) Movement resolution
  4) Combat resolution
  5) Capture/control updates
  6) Production/repair/upkeep
  7) Visibility update
  8) State broadcast

### 2.13 Victory, Draws, and Tie-Breakers
- Default win: last remaining player with a living Chief.
- Hard time limit: if reached:
  - Tie-breaker score = Chiefs alive (weight 1000) + total Facilities (weight 50) + total units alive (weight 1) + total resources (0.1).
  - Highest score wins; tie on score => draw.

### 2.14 Bot/API Specification (MVP)
- Transport: WebSocket for real-time; REST fallback for initialization.
- Authentication: Token per player; scoped to match_id.
- Server-to-bot messages (JSON):
  - match_start: map seed, config, your_player_id
  - state_tick: tick_id, your_visible_state, last_orders_status
  - match_end: result, summary
- Bot-to-server messages:
  - submit_orders: tick_target, orders[]
- Orders:
  - Move: {unit_id, dest_q, dest_r}
  - Produce: {facility_id, unit_type}
  - Disband: {unit_id}
  - SetRally: {facility_id, q, r}
- Validation:
  - Illegal orders rejected with error code and reason.
- Rate limits: 50 orders/tick; total payload < 64KB/tick.

### 2.15 Dashboard and Spectator
- Player view:
  - Fog-of-war respected; unit counts at frontier summarized.
  - Map layers: control, visibility, production queues, resource overlay.
  - Event feed: combats, captures, unit completions, Chief status.
- Spectator:
  - Post-match replays only, or admin live with full-vision toggle.

### 2.16 Performance, Limits, and Anti-Cheat
- Limits:
  - Max units/player: 300
  - Max facilities/player: 10
  - Max map cells: 25600
- Anti-cheat:
  - Server-authoritative simulation; sandboxed bot connections; deterministic logs.
- Replays:
  - Full deterministic replay from seed + orders log.

### 2.17 Localization and Accessibility
- Text keys externalized; UTF-8 throughout.
- Colorblind-friendly palettes for control/teams.
- Keyboard navigation and zoom options in dashboard.

### 2.18 Configuration Summary (Editable)
- Tick duration, map size, resource node density, stack cap, upkeep rates, tie-breaker weights.



## 3) Example Data Schemas (Concise) 📦

- State tick (partial):
  - tick_id
  - you: {resources: {M,F,I}, facilities[], units[]}
  - visible_hexes: [{q,r, terrain, owner_id?, enemy_unit_counts?}]
  - events: [{type, at:{q,r}, details}]

- Orders (sample):
  - {type:"Move", unit_id:"u123", dest_q:10, dest_r:-3}
  - {type:"Produce", facility_id:"f12", unit_type:"Armored"}

- Error codes:
  - ORD-001 InvalidDestination
  - ORD-002 StackCapExceeded
  - ORD-003 InsufficientResources
  - ORD-004 LateSubmission
  - ORD-005 NotVisibleOrOwned


## 4) Edge Cases and Clarifications 🧪

- Simultaneous entry into hex with defender:
  - If defender remains after combat, attackers that failed to dislodge return to prior hex (if available) or stay and stack if cap allows; if neither, they are displaced back and marked “disrupted” (-1 MP next tick).
- Chief on Facility:
  - Chiefs do not block production but count toward stack cap.
- Disconnected supply:
  - Supply recalculated after movement and control updates each tick.
- Multiple combats:
  - Max 3 rounds per hex per tick to cap runtime.
- Elimination:
  - Upon Chief death/capture: all units and facilities transfer to neutral; any co-located enemy unit may capture facilities next tick.

## 5) MVP vs Future Enhancements 🚀

- MVP:
  - Systems defined above.
- Future:
  - Ranged units, artillery, air recon.
  - Weather affecting movement/vision.
  - Diplomacy/alliances.
  - Tech branches and commander abilities.
  - Terrain destruction and buildable roads.


## 6) I want to 👍

- Remove ambiguity with precise, deterministic rules.
- Provide fair map generation and balanced starts.
- Define a complete economy, unit roster, combat, supply, and visibility system.
- Supply a clear tick order and bot API for scripted players.
- Include dashboard requirements, replay support, and operational constraints.


# JSON Schemas + Balanced Resource Starts 🎮🧩

Below are minimal, implementation-ready JSON Schemas for:
- state_tick (server-to-bot)
- submit_orders (bot-to-server)

Then, suggested balanced starting resource distributions per player count (2–6 players), including safe vs contested nodes and yields.

## 1) JSON Schema: state_tick 🛰️

```json
{
  "$id": "https://example.com/schemas/state_tick.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "state_tick",
  "type": "object",
  "additionalProperties": false,
  "required": ["tick_id", "you", "visible_hexes", "events"],
  "properties": {
    "tick_id": { "type": "integer", "minimum": 0 },
    "you": {
      "type": "object",
      "additionalProperties": false,
      "required": ["player_id", "resources", "facilities", "units"],
      "properties": {
        "player_id": { "type": "string", "minLength": 1 },
        "resources": {
          "type": "object",
          "additionalProperties": false,
          "required": ["M", "F", "I"],
          "properties": {
            "M": { "type": "integer", "minimum": 0 },
            "F": { "type": "integer", "minimum": 0 },
            "I": { "type": "integer", "minimum": 0 }
          }
        },
        "facilities": {
          "type": "array",
          "items": { "$ref": "#/$defs/Facility" }
        },
        "units": {
          "type": "array",
          "items": { "$ref": "#/$defs/Unit" }
        }
      }
    },
    "visible_hexes": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["q", "r", "terrain"],
        "properties": {
          "q": { "type": "integer" },
          "r": { "type": "integer" },
          "terrain": {
            "type": "string",
            "enum": ["Plains", "Hills", "Forest", "City", "Impassable"]
          },
          "owner_id": { "type": "string" },
          "enemy_unit_counts": {
            "type": "object",
            "additionalProperties": false,
            "properties": {
              "total": { "type": "integer", "minimum": 0 },
              "by_type": {
                "type": "object",
                "additionalProperties": { "type": "integer", "minimum": 0 },
                "propertyNames": { "pattern": "^(LightInfantry|Scout|Armored|Mechanized|SpecialForces|Chief)$" }
              }
            }
          }
        }
      }
    },
    "events": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": true,
        "required": ["type", "at"],
        "properties": {
          "type": {
            "type": "string",
            "enum": ["Combat", "Capture", "UnitBuilt", "ChiefEliminated", "OrderRejected"]
          },
          "at": {
            "type": "object",
            "additionalProperties": false,
            "required": ["q", "r"],
            "properties": {
              "q": { "type": "integer" },
              "r": { "type": "integer" }
            }
          },
          "details": { "type": "object" }
        }
      }
    }
  },
  "$defs": {
    "Unit": {
      "type": "object",
      "additionalProperties": false,
      "required": ["unit_id", "type", "q", "r", "hp", "mp", "vision"],
      "properties": {
        "unit_id": { "type": "string", "minLength": 1 },
        "type": {
          "type": "string",
          "enum": ["LightInfantry", "Scout", "Armored", "Mechanized", "SpecialForces", "Chief"]
        },
        "q": { "type": "integer" },
        "r": { "type": "integer" },
        "hp": { "type": "integer", "minimum": 0 },
        "mp": { "type": "integer", "minimum": 0 },
        "vision": { "type": "integer", "minimum": 0 }
      }
    },
    "Facility": {
      "type": "object",
      "additionalProperties": false,
      "required": ["facility_id", "q", "r", "slots", "production_queue"],
      "properties": {
        "facility_id": { "type": "string", "minLength": 1 },
        "q": { "type": "integer" },
        "r": { "type": "integer" },
        "slots": { "type": "integer", "minimum": 1 },
        "production_queue": {
          "type": "array",
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["unit_type", "ticks_remaining"],
            "properties": {
              "unit_type": {
                "type": "string",
                "enum": ["LightInfantry", "Scout", "Armored", "Mechanized", "SpecialForces", "Chief"]
              },
              "ticks_remaining": { "type": "integer", "minimum": 0 }
            }
          }
        }
      }
    }
  }
}
```

---

## 2) JSON Schema: submit_orders 📤

```json
{
  "$id": "https://example.com/schemas/submit_orders.schema.json",
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "submit_orders",
  "type": "object",
  "additionalProperties": false,
  "required": ["tick_target", "orders"],
  "properties": {
    "tick_target": {
      "type": "integer",
      "minimum": 0,
      "description": "Server applies orders at this tick if received before deadline."
    },
    "orders": {
      "type": "array",
      "maxItems": 50,
      "items": {
        "oneOf": [
          { "$ref": "#/$defs/Move" },
          { "$ref": "#/$defs/Produce" },
          { "$ref": "#/$defs/Disband" },
          { "$ref": "#/$defs/SetRally" }
        ]
      }
    }
  },
  "$defs": {
    "UnitType": {
      "type": "string",
      "enum": ["LightInfantry", "Scout", "Armored", "Mechanized", "SpecialForces", "Chief"]
    },
    "Move": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "unit_id", "dest_q", "dest_r"],
      "properties": {
        "type": { "const": "Move" },
        "unit_id": { "type": "string", "minLength": 1 },
        "dest_q": { "type": "integer" },
        "dest_r": { "type": "integer" }
      }
    },
    "Produce": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "facility_id", "unit_type"],
      "properties": {
        "type": { "const": "Produce" },
        "facility_id": { "type": "string", "minLength": 1 },
        "unit_type": { "$ref": "#/$defs/UnitType" }
      }
    },
    "Disband": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "unit_id"],
      "properties": {
        "type": { "const": "Disband" },
        "unit_id": { "type": "string", "minLength": 1 }
      }
    },
    "SetRally": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type", "facility_id", "q", "r"],
      "properties": {
        "type": { "const": "SetRally" },
        "facility_id": { "type": "string", "minLength": 1 },
        "q": { "type": "integer" },
        "r": { "type": "integer" }
      }
    }
  }
}
```

Notes:
- Schema enforces known order types via oneOf and const.
- Rate limit baked in as maxItems: 50.
- Cross-tick timing validation (e.g., must be ≥ current_tick+1) should be enforced server-side, not via schema.

---

## 3) Balanced Starting Resources by Player Count ⚖️

Baseline yields per node (configurable):
- Materials node: 6 M/tick
- Fuel node: 4 F/tick
- Intel node: 3 I/tick

Safe nodes per player (spawn-adjacent, easy to secure):
- 2 Materials nodes
- 1 Fuel node
- 1 Intel node

Contested nodes scale with player count to keep tension while preserving fair early game. Starting resource pools stay constant across player counts for predictability.

Recommended starting resources (per player, all counts):
- Materials (M): 320
- Fuel (F): 70
- Intel (I): 50

Contested nodes (total across the whole map):
- 2 players:
  - Materials: 2
  - Fuel: 1
  - Intel: 1
- 3 players:
  - Materials: 3
  - Fuel: 2
  - Intel: 2
- 4 players:
  - Materials: 4
  - Fuel: 2
  - Intel: 2
- 5 players:
  - Materials: 5
  - Fuel: 3
  - Intel: 3
- 6 players:
  - Materials: 6
  - Fuel: 3
  - Intel: 3

Why this works:
- Starting pool supports immediate builds like: 4x LightInfantry (160M) + 1x Scout (50M/10I) + 1x Armored (120M/40F) with buffer remaining.
- Safe nodes guarantee sustainable production; contested ring scales with players to create fair mid-map pressure.
- Uniform starting pools simplify bot tuning and keep early game consistent across player counts.

Optional scaling variant (if you prefer ramping with larger maps or longer matches):
- Increase starting M/F/I by +10% for Large maps or +5% when players ≥5.
- Or add +1 safe Materials node per player when players ≥5 to reduce early starvation in crowded spawns.

---

## 4) Implementation Tips 🛠️

- Determinism: Keep RNG seeded by match_id and tick; avoid per-client randomness.
- Validation: Schema validates shape; server must still validate legality (ownership, visibility, stack caps, deadlines).
- Evolution: Use $id versions (e.g., .../v1/state_tick.schema.json) and include schema version in messages for backward compatibility.

If you want, I can also provide:
- Example valid JSON payloads for each schema.
- A compact TypeScript type definition generated from these schemas.
- A seedable RNG function signature and usage for combat rolls.
