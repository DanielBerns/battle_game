import asyncio
from typing import Dict, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from contextlib import asynccontextmanager

from shared.schemas import (
    MatchStart, MapData, GameConstants, GameState,
    OrderSubmission, Order, UnitState, HexCoord, Resources,
    UnitType
)
from server.engine import GameEngine

# --- Global In-Memory Store ---
# In a real production app, this would be Redis + Postgres
games: Dict[str, GameEngine] = {}
# Buffer for incoming orders: match_id -> [Order]
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
            # engine.process_tick returns a NEW state object (immutable style)
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
def match_start(match_id: str):
    """
    Initializes a match if it doesn't exist.
    """
    if match_id not in games:
        print(f"Initializing Match: {match_id}")
        engine = GameEngine(match_id)

        # Initialize with some dummy units for testing
        # (In a real game, this comes from a 'Lobby' phase)
        engine.current_state = GameState(
            tick=0,
            game_status="ACTIVE",
            you={
                "resources": Resources(M=1000, F=500, I=0),
                "units": [
                    # Red Unit (Bot 1) at (0,0)
                    UnitState(id="u_red_1", type=UnitType.ARMORED, q=0, r=0, hp=120, mp=1, owner="p_red"),
                    # Blue Unit (Bot 2) at (0,4) - Close enough to move and fight
                    UnitState(id="u_blue_1", type=UnitType.ARMORED, q=0, r=4, hp=120, mp=1, owner="p_blue"),
                ],
                "facilities": []
            },
            visible_changes={"units": [], "control_updates": []},
            events=[]
        )

        games[match_id] = engine
        order_buffers[match_id] = []

    # Static Map Data
    return MatchStart(
        match_id=match_id,
        my_id="p_unknown", # Client will overwrite this with their token logic
        map=MapData(
            width=20,
            height=20,
            static_terrain=[]
        ),
        constants=GameConstants()
    )

@app.get("/match/{match_id}/state")
def get_state(match_id: str):
    if match_id not in games:
        raise HTTPException(status_code=404, detail="Match not found")

    # Return the current dynamic state
    return games[match_id].current_state

@app.post("/match/{match_id}/orders")
def submit_orders(match_id: str, submission: OrderSubmission):
    if match_id not in games:
        raise HTTPException(status_code=404, detail="Match not found")

    # Add orders to the buffer for the NEXT tick
    # (Note: Race condition possible in heavy prod, use Redis/Queue in real life)
    if match_id not in order_buffers:
        order_buffers[match_id] = []

    order_buffers[match_id].extend(submission.orders)

    return {"status": "queued", "count": len(submission.orders)}
