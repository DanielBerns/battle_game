# server/main.py
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

# Import our shared schemas and engine
from shared.schemas import MatchStart, MapData, GameConstants, GameState, UnitState, HexCoord, Resources
from server.database import get_db, Base, engine
from server.engine import GameEngine

# Create DB tables (Simple auto-migration for dev)
Base.metadata.create_all(bind=engine)

app = FastAPI()

# In-memory Simulation State (For this prototype)
# In production, this would be loaded/saved to Redis or DB
active_engines = {}

@app.get("/")
def health_check():
    return {"status": "ok", "service": "Battle Game v2.0"}

@app.post("/match/{match_id}/join")
def join_match(match_id: str, db: Session = Depends(get_db)):
    """
    Simple endpoint to initialize a match engine if it doesn't exist.
    """
    if match_id not in active_engines:
        active_engines[match_id] = GameEngine(match_id)
    return {"status": "joined", "match_id": match_id}

@app.get("/match/{match_id}/start")
def match_start(match_id: str):
    """
    Returns static initialization data (Map, Constants).
    """
    # 1. Initialize Engine if needed
    if match_id not in active_engines:
        active_engines[match_id] = GameEngine(match_id)

    # 2. Return Static Data (Mock 10x10 Map)
    return MatchStart(
        match_id=match_id,
        my_id="player_1", # In real app, verify token to determine ID
        map=MapData(
            width=10,
            height=10,
            static_terrain=[{"q":0, "r":0, "type":"Mountain"}]
        ),
        constants=GameConstants()
    )

@app.get("/match/{match_id}/state")
def get_state(match_id: str):
    """
    Returns the current game state.
    """
    if match_id not in active_engines:
        raise HTTPException(status_code=404, detail="Match not found")

    # Create a dummy state for now so the bot doesn't crash
    # The Engine usually produces this.
    return GameState(
        tick=active_engines[match_id].tick if hasattr(active_engines[match_id], 'tick') else 0,
        game_status="ACTIVE",
        you={
            "resources": Resources(M=100, F=50, I=0),
            "units": [
                # Give the bot one unit to control
                UnitState(id="u1", type="Scout", q=0, r=0, hp=40, mp=3, owner="player_1")
            ],
            "facilities": []
        },
        visible_changes={"units": [], "control_updates": []},
        events=[]
    )

@app.post("/match/{match_id}/orders")
def submit_orders(match_id: str):
    # Stub to accept orders without crashing
    return {"status": "received"}
