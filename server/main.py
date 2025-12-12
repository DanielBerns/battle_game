import asyncio
import json
import os
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from contextlib import asynccontextmanager

from shared.schemas import (
    MatchStart, MapData, GameConstants, GameState,
    OrderSubmission, Order, UnitState, HexCoord, Resources,
    UnitType, GameStatus
)
from server.engine import GameEngine

# --- Configuration Loading Helpers ---

CONFIG_DIR = os.getenv("CONFIG_DIR", "configs")

def load_game_config(match_id: str):
    """Loads {match_id}.json to find player config filenames."""
    path = os.path.join(CONFIG_DIR, f"{match_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Game config not found: {path}")

    with open(path, 'r') as f:
        return json.load(f)

def load_player_config(filename: str):
    """Loads a player .json file to extract the token."""
    path = os.path.join(CONFIG_DIR, filename)
    with open(path, 'r') as f:
        return json.load(f)

def get_player_id_from_filename(filename: str) -> str:
    """Extracts 'p_red' from 'p_red.json'"""
    return os.path.splitext(os.path.basename(filename))[0]

# Load Game Parameters (Static Global)
try:
    # Assuming parameters.json is still static for game rules
    param_path = os.path.join(os.path.dirname(__file__), "parameters.json")
    with open(param_path, 'r') as f:
        GAME_PARAMS = json.load(f)
except Exception as e:
    print(f"Warning: Could not load parameters.json: {e}")
    GAME_PARAMS = {
        "resources": {"M": 1000, "F": 500, "I": 0},
        "initial_units": []
    }

# --- Global State ---
games: Dict[str, GameEngine] = {}
order_buffers: Dict[str, List[Order]] = {}
# Map match_id -> { token -> player_id }
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
            # NEW: Only process tick if game is ACTIVE
            if engine.current_state.game_status != GameStatus.ACTIVE:
                continue
            current_orders = order_buffers.get(match_id, [])
            new_state = engine.process_tick(engine.current_state, current_orders)
            engine.current_state = new_state
            order_buffers[match_id] = []

            if new_state.tick % 5 == 0:
                print(f"Match {match_id}: Tick {new_state.tick} processed.")

# --- Helper: Authentication ---

def get_player_from_token(match_id: str, token: str) -> str:
    """Resolves token to player_id for a specific match."""
    # 1. Observer check
    if not token or token == "observer":
        return "p_observer"

    # 2. Check loaded match auth
    if match_id in match_auth_tables:
        return match_auth_tables[match_id].get(token, "p_observer")

    return "p_observer"

@app.get("/")
def health_check():
    return {"status": "ok", "active_matches": list(games.keys())}

@app.get("/match/{match_id}/start")
def match_start(match_id: str, request: Request):
    # 1. Lazy Load Match Configuration if not active
    if match_id not in games:
        print(f"Initializing Match: {match_id} from config file.")
        try:
            game_config = load_game_config(match_id)

            # Build Auth Table for this match
            auth_table = {}
            for p_file in game_config.get("players", []):
                p_data = load_player_config(p_file)
                p_id = get_player_id_from_filename(p_file)
                p_token = p_data.get("token")
                if p_token:
                    auth_table[p_token] = p_id

            match_auth_tables[match_id] = auth_table

            # Initialize Engine
            engine = GameEngine(match_id)

            # Load initial state from parameters.json
            res_cfg = GAME_PARAMS.get("resources", {})
            resources = Resources(M=res_cfg.get("M", 0), F=res_cfg.get("F", 0), I=res_cfg.get("I", 0))

            initial_units = []
            for u in GAME_PARAMS.get("initial_units", []):
                try:
                    initial_units.append(UnitState(
                        id=u["id"], type=UnitType(u["type"]),
                        q=u["q"], r=u["r"], hp=u["hp"], mp=u["mp"], owner=u["owner"]
                    ))
                except Exception as e:
                    print(f"Error loading unit {u}: {e}")

            # NEW: Initialize with WAITING instead of ACTIVE
            engine.current_state = GameState(
                tick=0, game_status=GameStatus.WAITING,
                you={"resources": resources, "units": initial_units, "facilities": []},
                visible_changes={"units": [], "control_updates": []}, events=[]
            )

            games[match_id] = engine
            order_buffers[match_id] = []

        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=f"Config not found: {e}")
        except Exception as e:
            print(f"Failed to start match: {e}")
            raise HTTPException(status_code=500, detail="Internal Server Error during init")

    # 2. Authenticate Request
    token = request.headers.get("Authorization")
    player_id = get_player_from_token(match_id, token)

    return MatchStart(
        match_id=match_id,
        my_id=player_id,
        map=MapData(width=20, height=20, static_terrain=[]),
        constants=GameConstants()
    )


@app.get("/match/{match_id}/state")
def get_state(match_id: str, request: Request):
    if match_id not in games:
        raise HTTPException(status_code=404, detail="Match not found")

    token = request.headers.get("Authorization")
    player_id = get_player_from_token(match_id, token)

    global_state = games[match_id].current_state

    # Observer sees everything
    if player_id == "p_observer":
        return global_state

    # Filter for player
    my_units = [u for u in global_state.you.units if u.owner == player_id]
    # Simple FoW stub: see all enemies (refine logic as needed)
    visible_enemies = [u for u in global_state.you.units if u.owner != player_id]

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

@app.post("/match/{match_id}/start")
def start_match(match_id: str):
    if match_id not in games:
        raise HTTPException(status_code=404, detail="Match not found")

    games[match_id].current_state.game_status = GameStatus.ACTIVE
    print(f"Match {match_id} STARTED by Dashboard!")
    return {"status": "started"}
