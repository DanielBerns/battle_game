import asyncio
import json
import os
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from contextlib import asynccontextmanager

from shared.schemas import (
    MatchStart, MapData, GameConstants, GameState,
    OrderSubmission, Order, UnitState, HexCoord, Resources,
    UnitType
)
from server.engine import GameEngine

# --- Configuration Loading ---

def load_json_config(filename: str):
    path = os.path.join(os.path.dirname(__file__), filename)
    with open(path, 'r') as f:
        return json.load(f)

# Load Players Configuration
try:
    PLAYERS_CONFIG = load_json_config("players.json")
    # Create a quick lookup map: token -> player_id
    TOKEN_TO_ID = {p["token"]: p["id"] for p in PLAYERS_CONFIG.get("players", [])}
except Exception as e:
    print(f"Warning: Could not load players.json: {e}")
    TOKEN_TO_ID = {}

# Load Game Parameters
try:
    GAME_PARAMS = load_json_config("parameters.json")
except Exception as e:
    print(f"Warning: Could not load parameters.json: {e}")
    GAME_PARAMS = {
        "resources": {"M": 1000, "F": 500, "I": 0},
        "initial_units": []
    }

# --- Global In-Memory Store ---
games: Dict[str, GameEngine] = {}
order_buffers: Dict[str, List[Order]] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: Launch the background ticker
    task = asyncio.create_task(game_ticker())
    yield
    # SHUTDOWN
    task.cancel()

app = FastAPI(lifespan=lifespan)

async def game_ticker():
    """
    The Heartbeat: Advances all active games by 1 tick every second.
    """
    print("--- Game Ticker Started ---")
    while True:
        await asyncio.sleep(1.0) # 1 Tick = 1 Second

        # Iterate over all active matches
        for match_id, engine in games.items():
            # 1. Get queued orders for this tick
            current_orders = order_buffers.get(match_id, [])

            # 2. Process the tick (Movement -> Combat)
            new_state = engine.process_tick(engine.current_state, current_orders)

            # 3. Update the engine state
            engine.current_state = new_state

            # 4. Clear the buffer for the next tick
            order_buffers[match_id] = []

            if new_state.tick % 5 == 0:
                print(f"Match {match_id}: Tick {new_state.tick} processed. Units: {len(new_state.you.units)}")

@app.get("/")
def health_check():
    return {"status": "ok", "active_matches": list(games.keys())}

@app.get("/match/{match_id}/start")
def match_start(match_id: str, request: Request):
    """
    Initializes a match if it doesn't exist.
    Identifies the player based on the Authorization header.
    """
    # 1. Identify Player
    token = request.headers.get("Authorization")
    player_id = TOKEN_TO_ID.get(token, "p_observer")

    # 2. Initialize Match if needed
    if match_id not in games:
        print(f"Initializing Match: {match_id} with params from config.")
        engine = GameEngine(match_id)

        # Load resources from config
        res_cfg = GAME_PARAMS.get("resources", {})
        resources = Resources(
            M=res_cfg.get("M", 0),
            F=res_cfg.get("F", 0),
            I=res_cfg.get("I", 0)
        )

        # Load units from config
        initial_units = []
        for u in GAME_PARAMS.get("initial_units", []):
            try:
                # Convert string type to Enum
                u_type = UnitType(u["type"])
                unit = UnitState(
                    id=u["id"],
                    type=u_type,
                    q=u["q"],
                    r=u["r"],
                    hp=u["hp"],
                    mp=u["mp"],
                    owner=u["owner"]
                )
                initial_units.append(unit)
            except ValueError as e:
                print(f"Error loading unit {u.get('id')}: {e}")

        engine.current_state = GameState(
            tick=0,
            game_status="ACTIVE",
            you={
                "resources": resources,
                "units": initial_units,
                "facilities": []
            },
            visible_changes={"units": [], "control_updates": []},
            events=[]
        )

        games[match_id] = engine
        order_buffers[match_id] = []

    # 3. Return Match Data
    return MatchStart(
        match_id=match_id,
        my_id=player_id, # Dynamically assigned from token
        map=MapData(
            width=20,
            height=20,
            static_terrain=[]
        ),
        constants=GameConstants()
    )

@app.get("/match/{match_id}/state")
def get_state(match_id: str, request: Request):
    if match_id not in games:
        raise HTTPException(status_code=404, detail="Match not found")

    # 1. Identify Player
    token = request.headers.get("Authorization")
    player_id = TOKEN_TO_ID.get(token, "p_observer")

    global_state = games[match_id].current_state

    # If observer (Dashboard), return full state so it can see everything
    if player_id == "p_observer":
        return global_state

    # 2. Filter Units for Players
    my_units = []
    visible_enemies = []

    for unit in global_state.you.units:
        if unit.owner == player_id:
            my_units.append(unit)
        else:
            visible_enemies.append(unit)

    # 3. Construct Player View
    # We copy the global state structure but replace the lists with filtered versions
    player_view = global_state.model_copy()

    player_view.you = global_state.you.model_copy()
    player_view.you.units = my_units

    player_view.visible_changes = global_state.visible_changes.model_copy()
    player_view.visible_changes.units = visible_enemies

    return player_view

@app.post("/match/{match_id}/orders")
def submit_orders(match_id: str, submission: OrderSubmission):
    if match_id not in games:
        raise HTTPException(status_code=404, detail="Match not found")

    if match_id not in order_buffers:
        order_buffers[match_id] = []

    order_buffers[match_id].extend(submission.orders)

    return {"status": "queued", "count": len(submission.orders)}
