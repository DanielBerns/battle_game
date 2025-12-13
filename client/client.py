import time
import os
import sys
import json
import httpx
import logging
from sqlalchemy import create_engine, Column, String, Integer, Float
from sqlalchemy.orm import declarative_base, Session

from shared.schemas import (
    OrderSubmission, Order, OrderType, HexCoord,
    GameState, MatchStart, UnitType
)
from shared.hex_math import Hex, hex_distance, hex_neighbors
from shared.unique_ids import unique_id

# --- Logging Setup ---
logger = logging.getLogger("battle_bot")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler(f'client_{unique_id()}.log')
log_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(log_format)
file_handler.setFormatter(log_format)
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
    def __init__(self, server_url: str, match_id: str, config_file: str):
        self.server_url = server_url
        self.match_id = match_id
        self.config_file = config_file
        self.map_data = None

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                self.token = config.get("token")
                self.derived_id = os.path.splitext(os.path.basename(config_file))[0]
        except Exception as e:
            logger.error(f"Failed to load config file {config_file}: {e}")
            sys.exit(1)

        logger.info(f"Initialized Aggressive Bot {self.derived_id} using config {config_file}")
        self.client = httpx.Client(base_url=server_url, timeout=5.0)
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.last_tick = -1
        self.my_id = "unknown"

    def start(self):
        logger.info(f"Connecting to match {self.match_id}...")
        while True:
            try:
                resp = self.client.get(f"/match/{self.match_id}/start", headers={"Authorization": self.token})
                if resp.status_code == 200:
                    break
            except Exception as e:
                logger.debug(f"Connection attempt failed: {e}")
                pass
            logger.info("Waiting for server...")
            time.sleep(2)

        data = MatchStart(**resp.json())
        self.my_id = data.my_id
        self.map_data = data.map
        logger.info(f"Connected as {self.my_id}. Map size: {self.map_data.width}x{self.map_data.height}")
        self._run_loop()

    def _run_loop(self):
        while True:
            try:
                state_resp = self.client.get(f"/match/{self.match_id}/state", headers={"Authorization": self.token})
                if state_resp.status_code != 200:
                    time.sleep(1)
                    continue

                game_state = GameState(**state_resp.json())

                if game_state.tick <= self.last_tick:
                    time.sleep(0.1)
                    continue

                self.last_tick = game_state.tick
                # logger.info(f"Processing Tick {game_state.tick}")

                orders = self._logic(game_state)

                if orders:
                    # Log the orders being sent
                    move_orders = len([o for o in orders if o.type == OrderType.MOVE])
                    build_orders = len([o for o in orders if o.type == OrderType.BUILD])
                    logger.info(f"Submitting {len(orders)} orders (Moves: {move_orders}, Builds: {build_orders})")

                    submission = OrderSubmission(tick=game_state.tick + 1, orders=orders)
                    self.client.post(
                        f"/match/{self.match_id}/orders",
                        json=submission.model_dump(),
                        headers={"Authorization": self.token}
                    )
                else:
                    logger.info("No orders generated this tick.")

            except Exception as e:
                logger.error(f"Error in game loop: {e}", exc_info=True)
                time.sleep(1)

    def _logic(self, game_state: GameState) -> list[Order]:
        orders = []
        resources = game_state.you.resources
        my_units = game_state.you.units
        visible_enemies = game_state.visible_changes.units

        # --- LOGGING STATE ---
        logger.info(f"[Tick {game_state.tick}] Resources: M={resources.M} F={resources.F} | My Units: {len(my_units)} | Visible Enemies: {len(visible_enemies)}")

        # Locate Key Units
        my_chief = next((u for u in my_units if u.type == UnitType.CHIEF), None)
        enemy_chief = next((u for u in visible_enemies if u.type == UnitType.CHIEF), None)

        logger.info(f"my_chief: {str(my_chief)} - enemy_chief: {str(enemy_chief)}")

        # Calculate strategic direction
        if my_units:
            avg_q = sum(u.q for u in my_units) / len(my_units)
            avg_r = sum(u.r for u in my_units) / len(my_units)
            strategic_target = Hex(15, 15) if (avg_q + avg_r) < 0 else Hex(-15, -15)
        else:
            strategic_target = Hex(0, 0)

        logger.info(f"strategic_target: {str(strategic_target)}")

        # --- 1. Aggressive Build Logic ---
        my_facilities = [f for f in game_state.you.facilities if f.owner == self.my_id]

        for fac in my_facilities:
            if resources.M >= 120 and resources.F >= 40:
                logger.info(f"  -> Order: Build ARMORED at {fac.id}")
                orders.append(Order(type=OrderType.BUILD, fac_id=fac.id, unit=UnitType.ARMORED))
                resources.M -= 120
                resources.F -= 40
            elif resources.M >= 40:
                logger.info(f"  -> Order: Build INFANTRY at {fac.id}")
                orders.append(Order(type=OrderType.BUILD, fac_id=fac.id, unit=UnitType.LIGHT_INFANTRY))
                resources.M -= 40

        # --- 2. Unit Logic ---
        for unit in my_units:
            logger.info(f"{unit.type} at ({unit.q},{unit.r}) - {unit.hp} - {unit.mp}")
            if unit.mp <= 0: continue

            u_hex = Hex(unit.q, unit.r)

            # A. Chief Logic (Survival)
            if unit.type == UnitType.CHIEF:
                logger.info("Chief unit")
                threats = [e for e in visible_enemies if hex_distance(u_hex, Hex(e.q, e.r)) <= 4]
                if threats:
                    logger.info(f"  -> Threats: {len(threats)}")
                    # ... (Kiting logic same as before) ...
                    avg_t_q = sum(e.q for e in threats) / len(threats)
                    avg_t_r = sum(e.r for e in threats) / len(threats)
                    threat_center = Hex(int(avg_t_q), int(avg_t_r))

                    best_escape = None
                    max_dist = -1
                    for n in hex_neighbors(u_hex):
                        if any(e.q == n.q and e.r == n.r for e in visible_enemies): continue
                        d = hex_distance(n, threat_center)
                        if d > max_dist:
                            max_dist = d
                            best_escape = n

                    if best_escape:
                        orders.append(Order(type=OrderType.MOVE, id=unit.id, dest=HexCoord(q=best_escape.q, r=best_escape.r)))
                        logger.info(f"  -> Chief fleeing to {best_escape} (away from {len(threats)} threats)")
                else:
                    logger.info(f"  -> Chief is safe")
                continue
            else:
                logger.info(f"Other units")

            # B. Combat Logic
            logger.info("Combat Logic")
            target_hex = strategic_target
            target_desc = "Strategic Base"

            if enemy_chief:
                target_hex = Hex(enemy_chief.q, enemy_chief.r)
                target_desc = "Enemy Chief"
                logger.info(f"  -> {str(target_hex)} {target_desc}")
            elif visible_enemies:
                closest = min(visible_enemies, key=lambda e: hex_distance(u_hex, Hex(e.q, e.r)))
                target_hex = Hex(closest.q, closest.r)
                target_desc = f"Enemy Unit at {target_hex}"
                logger.info(f"  -> {str(target_hex)} {target_desc} {closest}")
            else:
                logger.info(f"  -> {str(target_hex)} {target_desc}")

            # Move towards target
            logger.info("Move towards target")
            dist_to_target = hex_distance(u_hex, target_hex)
            logger.info(f"  -> dist_to_target {dist_to_target}")
            if dist_to_target > 0:
                best_move = None
                min_dist = 9999

                for n in hex_neighbors(u_hex):
                    d = hex_distance(n, target_hex)
                    if d < min_dist:
                        min_dist = d
                        best_move = n

                if best_move:
                    orders.append(Order(type=OrderType.MOVE, id=unit.id, dest=HexCoord(q=best_move.q, r=best_move.r)))
                    # Detailed log for verifying targeting
                    logger.debug(f"Unit {unit.id} targeting {target_desc} ({dist_to_target} hexes away). Move -> {best_move}")
                else:
                     logger.warning(f"Unit {unit.id} STUCK. Target: {target_hex}, Dist: {dist_to_target}")
            else:
                logger.info(f"  -> dist_to_target <= 0")

        return orders

if __name__ == "__main__":
    server_url = os.getenv("SERVER_URL", "http://localhost:8000")
    match_id = os.getenv("MATCH_ID", "m_debug_01")
    config_file = os.getenv("PLAYER_CONFIG_FILE")

    if not config_file:
        logger.error("PLAYER_CONFIG_FILE env var is required.")
        sys.exit(1)

    logger.info("Bot starting up, waiting 5s...")
    time.sleep(5)

    bot = Bot(server_url, match_id, config_file)
    bot.start()
