import httpx
from shared.schemas import Order

class Bot:
    def __init__(self, api_url, api_key):
        self.client = httpx.Client(base_url=api_url)

    def game_loop(self):
        while True:
            # 1. Fetch State
            state = self.client.get(f"/match/{self.match_id}/state").json()

            # 2. Update Local SQLite
            self.update_local_db(state)

            # 3. Decision Logic (The "Brain")
            orders = self.calculate_moves()

            # 4. Submit
            self.client.post(f"/match/{self.match_id}/orders", json=orders)

    def calculate_moves(self):
        # Example: Find weak enemies
        # SQL: SELECT * FROM units WHERE owner != 'me' AND hp < 20
        # Generate move orders to flank
        return []
