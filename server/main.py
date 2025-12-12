import asyncio
import json
import os
from typing import Dict, List, Optional, Tuple
from fastapi import FastAPI, HTTPException, Request
from contextlib import asynccontextmanager

from shared.schemas import (
    MatchStart, MapData, GameConstants, GameState,
    OrderSubmission, Order, UnitState, HexCoord, Resources,
    UnitType, GameStatus, GameInitRequest, PlayerState, VisibleChanges
)
from server.engine import GameEngine

CONFIG_DIR = os.getenv("CONFIG_DIR", "configs")

# --- Helpers ---
def load_game_config(match_id: str):
    path = os.path.join(CONFIG_DIR, f"{match_id}.json")
    if not os.path.exists(path): raise FileNotFoundError(path)
    with open(path, 'r') as f: return json.load(f)

def load_player_config(filename: str):
    path = os.path.join(CONFIG_DIR, filename)
    with open(path, 'r') as f: return json.load(f)

def get_player_id_from_filename(filename: str) -> str:
    return os.path.splitext(os.path.basename(filename))[0]

# --- Global State ---
games: Dict[str, GameEngine] = {}
# Buffer now stores (player_id, Order) tuples
order_buffers: Dict[str, List[Tuple[str, Order]]] = {}
match_auth_tables: Dict[str, Dict[str, str]] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(game_ticker())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

async def game_ticker():
    print("--- Game Ticker Started ---")
    while True:
        await asyncio.sleep(1.0)
        for match_id, engine in games.items():
            if engine.current_state and engine.current_state.game_status == GameStatus.ACTIVE:
                current_orders = order_buffers.get(match_id, [])
                new_state = engine.process_tick(engine.current_state, current_orders)
                engine.current_state = new_state
                order_buffers[match_id] = [] # Clear buffer

                if new_state.tick % 10 == 0:
                    print(f"Match {match_id}: Tick {new_state.tick}")

def get_player_from_token(match_id: str, token: str) -> str:
    if not token or token == "observer": return "p_observer"
    if match_id in match_auth_tables:
        return match_auth_tables[match_id].get(token, "p_observer")
    return "p_observer"

@app.get("/")
def health_check():
    return {"status": "ok", "active_matches": list(games.keys())}

# --- Initialization API ---

@app.post("/match/init")
def init_game(payload: GameInitRequest):
    """Dynamically initializes a match with specific resources."""
    engine = GameEngine(payload.match_id)
    engine.initialize_dynamic(payload.initial_resources)

    games[payload.match_id] = engine
    order_buffers[payload.match_id] = []

    # Register default dev tokens
    match_auth_tables[payload.match_id] = {
        "secret_red_token_123": "p_red",
        "secret_blue_token": "p_blue"
    }

    print(f"Match {payload.match_id} created. Resources: {payload.initial_resources}")
    return {"status": "created", "match_id": payload.match_id}

@app.post("/match/{match_id}/start")
def start_match(match_id: str):
    if match_id not in games:
        # Auto-init if not exists (fallback)
        print(f"Auto-initializing {match_id} with default resources.")
        engine = GameEngine(match_id)
        engine.initialize_dynamic(Resources(M=1000, F=500, I=200))
        games[match_id] = engine
        order_buffers[match_id] = []
        match_auth_tables[match_id] = {"secret_red_token_123": "p_red", "secret_blue_token": "p_blue"}

    games[match_id].current_state.game_status = GameStatus.ACTIVE
    return {"status": "started"}

@app.get("/match/{match_id}/start")
def match_config(match_id: str, request: Request):
    """GET endpoint for clients to fetch map/config."""
    # Ensure game exists
    if match_id not in games:
        # Trigger default init logic
        start_match(match_id)

    token = request.headers.get("Authorization")
    player_id = get_player_from_token(match_id, token)

    return MatchStart(
        match_id=match_id,
        my_id=player_id,
        map=MapData(width=20, height=20, static_terrain=[]),
        constants=GameConstants()
    )

# --- Game Loop API ---

@app.get("/match/{match_id}/state")
def get_state(match_id: str, request: Request):
    if match_id not in games:
        raise HTTPException(status_code=404, detail="Match not found")

    token = request.headers.get("Authorization")
    player_id = get_player_from_token(match_id, token)
    engine = games[match_id]
    global_state = engine.current_state

    # Observer View
    if player_id == "p_observer":
        # Hack: Observer sees p_red's resources just to show something
        view = global_state.model_copy()
        view.you = global_state.you.model_copy()
        view.you.resources = engine.player_resources.get("p_red", Resources())
        return view

    # Player View
    my_units = [u for u in global_state.you.units if u.owner == player_id]
    visible_enemies = [u for u in global_state.you.units if u.owner != player_id] # Simple FoW

    player_view = global_state.model_copy()
    player_view.you = PlayerState(
        resources=engine.player_resources.get(player_id, Resources()),
        units=my_units,
        facilities=global_state.you.facilities,
        unlocked_upgrades=engine.player_upgrades.get(player_id, [])
    )
    player_view.visible_changes = VisibleChanges(units=visible_enemies, control_updates=[])

    return player_view

@app.post("/match/{match_id}/orders")
def submit_orders(match_id: str, submission: OrderSubmission, request: Request):
    if match_id not in games:
        raise HTTPException(status_code=404, detail="Match not found")

    token = request.headers.get("Authorization")
    player_id = get_player_from_token(match_id, token)

    if player_id == "p_observer":
        return {"status": "ignored", "reason": "observer"}

    if match_id not in order_buffers:
        order_buffers[match_id] = []

    # Tag orders with player_id
    tagged_orders = [(player_id, order) for order in submission.orders]
    order_buffers[match_id].extend(tagged_orders)

    return {"status": "queued", "count": len(tagged_orders)}
