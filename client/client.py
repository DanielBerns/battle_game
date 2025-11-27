import os
import time
import httpx
from typing import List, Optional
from sqlalchemy import create_engine, Column, String, Integer, Float, select, delete
from sqlalchemy.orm import declarative_base, Session

# Import Shared Kernel
from shared.schemas import (
    OrderSubmission, Order, OrderType, HexCoord,
    UnitType, GameState, MatchStart
)
from shared.hex_math import Hex, hex_distance, hex_neighbors

# --- Local SQLite Mirror ---
Base = declarative_base()

class LocalUnit(Base):
    """
    Local cache of units for SQL-based decision making.
    """
    __tablename__ = "units"

    id = Column(String, primary_key=True)
    owner = Column(String, index=True) # 'me' or 'enemy'
    type = Column(String)
    q = Column(Integer)
    r = Column(Integer)
    hp = Column(Float)
    mp = Column(Integer)


class Bot:
    def __init__(self, server_url: str, match_id: str, secret_token: str):
        self.server_url = server_url
        self.match_id = match_id
        self.token = secret_token
        self.client = httpx.Client(base_url=server_url, timeout=5.0)

        # Initialize In-Memory SQLite Database
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        self.my_id = None
        self.map_data = None
        self.last_tick = -1

    def start(self):
        """Initial handshake to get static map data."""
        print(f"Connecting to match {self.match_id}...")
        resp = self.client.get(f"/match/{self.match_id}/start", headers={"Authorization": self.token})
        resp.raise_for_status()

        data = MatchStart(**resp.json())
        self.my_id = data.my_id
        self.map_data = data.map
        print(f"Connected as {self.my_id}. Map size: {self.map_data.width}x{self.map_data.height}")

        self._run_loop()

    def _run_loop(self):
        """Main OODA Loop."""
        while True:
            try:
                # 1. OBSERVE: Fetch latest state
                state_resp = self.client.get(f"/match/{self.match_id}/state")
                if state_resp.status_code != 200:
                    print("Waiting for match start...")
                    time.sleep(1)
                    continue

                game_state = GameState(**state_resp.json())

                # Prevent processing the same tick twice
                if game_state.tick <= self.last_tick:
                    time.sleep(0.1)
                    continue

                self.last_tick = game_state.tick
                print(f"--- Processing Tick {game_state.tick} ---")

                # 2. ORIENT: Update Local DB
                self._sync_state(game_state)

                # 3. DECIDE: logic()
                orders = self._logic(game_state.tick)

                # 4. ACT: Submit Orders
                if orders:
                    submission = OrderSubmission(tick=game_state.tick + 1, orders=orders)
                    self.client.post(
                        f"/match/{self.match_id}/orders",
                        json=submission.model_dump(),
                        headers={"Authorization": self.token}
                    )
                    print(f"Submitted {len(orders)} orders.")

            except Exception as e:
                print(f"Error in loop: {e}")
                time.sleep(1)

    def _sync_state(self, state: GameState):
        """
        Updates the SQLite mirror with the JSON data.
        """
        # A. Process Events (Deaths)
        for event in state.events:
            if event.type == "COMBAT":
                for casualty_id in event.details.casualties:
                    self.session.execute(delete(LocalUnit).where(LocalUnit.id == casualty_id))

        # B. Upsert MY units (Full State provided)
        # First, remove my old units to handle deaths implicitly if not caught by events
        self.session.execute(delete(LocalUnit).where(LocalUnit.owner == self.my_id))

        for u in state.you.units:
            unit = LocalUnit(
                id=u.id, owner=self.my_id, type=u.type,
                q=u.q, r=u.r, hp=u.hp, mp=u.mp
            )
            self.session.add(unit)

        # C. Upsert VISIBLE Enemies (Diff provided)
        # We assume enemies stay where they are unless we see them move or die
        for u in state.visible_changes.units:
            # Check if exists to update, or insert
            existing = self.session.get(LocalUnit, u.id)
            if existing:
                existing.q = u.q
                existing.r = u.r
                existing.hp = u.hp
            else:
                # Note: owner might not be in visible_changes explicitly if not defined in schema
                # We infer owner is NOT me.
                enemy_owner = u.owner if u.owner else "enemy_unknown"
                new_unit = LocalUnit(
                    id=u.id, owner=enemy_owner, type=u.type,
                    q=u.q, r=u.r, hp=u.hp, mp=0 # Don't know enemy MP usually
                )
                self.session.add(new_unit)

        self.session.commit()

    def _logic(self, current_tick: int) -> List[Order]:
        """
        The Strategy Brain.
        Example Strategy: "Aggressive Swarm" - Move everything toward the nearest enemy.
        """
        orders = []

        # Q1: Where are my units?
        my_units = self.session.execute(
            select(LocalUnit).where(LocalUnit.owner == self.my_id)
        ).scalars().all()

        # Q2: Where are the enemies?
        enemies = self.session.execute(
            select(LocalUnit).where(LocalUnit.owner != self.my_id)
        ).scalars().all()

        if not enemies:
            # No enemies visible? Move to center (0,0) to find them
            target_hex = Hex(0, 0)
        else:
            # Target the first enemy found (Simple Logic)
            target_hex = Hex(enemies[0].q, enemies[0].r)

        for unit in my_units:
            # Skip if no MP
            if unit.mp <= 0: continue

            # Simple Pathfinding: Move 1 step closer to target
            my_hex = Hex(unit.q, unit.r)

            if hex_distance(my_hex, target_hex) <= 1:
                # We are adjacent! Stay and fight (Combat is automatic on proximity)
                continue

            # Find neighbor closest to target
            best_move = None
            min_dist = 9999

            for neighbor in hex_neighbors(my_hex):
                # Check collision with terrain (requires looking up MapData, skipped for brevity)
                dist = hex_distance(neighbor, target_hex)
                if dist < min_dist:
                    min_dist = dist
                    best_move = neighbor

            if best_move:
                orders.append(Order(
                    type=OrderType.MOVE,
                    id=unit.id,
                    dest=HexCoord(q=best_move.q, r=best_move.r)
                ))

        return orders


if __name__ == "__main__":
    server_url = os.getenv("SERVER_URL", "http://localhost:8000")
    match_id = os.getenv("MATCH_ID", "m_local")
    token = os.getenv("BOT_TOKEN", "p_guest")

    # Wait for server to be ready (naive check)
    print(f"Bot sleeping 5s to allow server startup...")
    time.sleep(5)

    bot = Bot(server_url, match_id, token)
    bot.start()
