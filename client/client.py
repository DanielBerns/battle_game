import time
import os
import httpx
import logging
from sqlalchemy import create_engine, Column, String, Integer, Float, select, delete
from sqlalchemy.orm import declarative_base, Session

# Import Shared Kernel
from shared.schemas import (
    OrderSubmission, Order, OrderType, HexCoord,
    GameState, MatchStart
)
from shared.hex_math import Hex, hex_distance, hex_neighbors
from shared.unique_ids import unique_id

# --- Logging Configuration ---
# Configure the logger
logger = logging.getLogger("battle_bot")
logger.setLevel(logging.INFO)

# Create handlers
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler(f'client_{unique_id()}.log')

# Create formatters and add to handlers
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(log_format)
file_handler.setFormatter(log_format)

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

Base = declarative_base()

class LocalUnit(Base):
    __tablename__ = "units"
    id = Column(String, primary_key=True)
    owner = Column(String, index=True)
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

        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        self.my_id = None
        self.map_data = None
        self.last_tick = -1

    def start(self):
        logger.info(f"Connecting to match {self.match_id}...")
        while True:
            try:
                resp = self.client.get(f"/match/{self.match_id}/start", headers={"Authorization": self.token})
                if resp.status_code == 200:
                    break
            except Exception as e:
                # Log connection errors as debug to avoid cluttering logs during startup
                logger.debug(f"Connection attempt failed: {e}")
                pass

            logger.info("Waiting for server...")
            time.sleep(2)

        data = MatchStart(**resp.json())
        self.my_id = data.my_id
        self.map_data = data.map
        logger.info(f"Connected as {self.my_id}.")
        self._run_loop()

    def _run_loop(self):
        while True:
            try:
                state_resp = self.client.get(f"/match/{self.match_id}/state")
                if state_resp.status_code != 200:
                    time.sleep(1)
                    continue

                game_state = GameState(**state_resp.json())

                if game_state.tick <= self.last_tick:
                    time.sleep(0.1)
                    continue

                self.last_tick = game_state.tick
                logger.info(f"Processing Tick {game_state.tick}")

                self._sync_state(game_state)
                orders = self._logic(game_state.tick)

                if orders:
                    submission = OrderSubmission(tick=game_state.tick + 1, orders=orders)
                    self.client.post(
                        f"/match/{self.match_id}/orders",
                        json=submission.model_dump(),
                        headers={"Authorization": self.token}
                    )
                    logger.info(f"Submitted {len(orders)} orders for Tick {game_state.tick + 1}")
            except Exception as e:
                logger.error(f"Error in game loop: {e}", exc_info=True)
                time.sleep(1)

    def _sync_state(self, state: GameState):
        self.session.execute(delete(LocalUnit).where(LocalUnit.owner == self.my_id))
        for u in state.you.units:
            unit = LocalUnit(id=u.id, owner=self.my_id, type=u.type, q=u.q, r=u.r, hp=u.hp, mp=u.mp)
            self.session.add(unit)
        self.session.commit()

    def _logic(self, current_tick: int):
        orders = []
        my_units = self.session.execute(select(LocalUnit).where(LocalUnit.owner == self.my_id)).scalars().all()
        target_hex = Hex(0, 0) # Move to center

        for unit in my_units:
            if unit.mp <= 0: continue
            my_hex = Hex(unit.q, unit.r)
            if hex_distance(my_hex, target_hex) <= 1: continue

            best_move = None
            min_dist = 9999
            for neighbor in hex_neighbors(my_hex):
                dist = hex_distance(neighbor, target_hex)
                if dist < min_dist:
                    min_dist = dist
                    best_move = neighbor

            if best_move:
                orders.append(Order(type=OrderType.MOVE, id=unit.id, dest=HexCoord(q=best_move.q, r=best_move.r)))
        return orders

if __name__ == "__main__":
    server_url = os.getenv("SERVER_URL", "http://localhost:8000")
    match_id = os.getenv("MATCH_ID", "m_local")
    token = os.getenv("BOT_TOKEN", "p_guest")

    # Simple delay to ensure server is up
    logger.info("Bot starting up, waiting 5s...")
    time.sleep(5)

    bot = Bot(server_url, match_id, token)
    bot.start()
