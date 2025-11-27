from fastapi import FastAPI
from server.engine import GameEngine
from shared.schemas import MatchStart, MapData, GameConstants

app = FastAPI()

# In-memory store for debug
matches = {}

@app.get("/")
def health_check():
    return {"status": "ok"}

@app.get("/match/{match_id}/start")
def match_start(match_id: str):
    # Stub response to let bots connect
    return MatchStart(
        match_id=match_id,
        my_id="p_red", # Dynamic logic needed here based on token
        map=MapData(width=10, height=10, static_terrain=[]),
        constants=GameConstants()
    )

# ... add /state and /orders endpoints calling the Engine ...
