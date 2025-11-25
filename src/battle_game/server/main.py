from fastapi import FastAPI, Depends, HTTPException
from shared.schemas import OrderSubmission

app = FastAPI()

@app.post("/match/{match_id}/orders")
async def submit_orders(match_id: str, submission: OrderSubmission, user = Depends(get_current_user)):
    # 1. Validate constraints (Max 50 orders)
    # 2. Store in PostgreSQL 'pending_orders' column
    # 3. Wait for tick processing (usually done by a background worker/celery)
    pass

@app.get("/match/{match_id}/state")
async def get_state(match_id: str, tick: int):
    # Return the 'state_tick' JSON diff
    pass
