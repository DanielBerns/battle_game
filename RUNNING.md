# Running Battle Game V2

This document provides complete instructions for running the Battle Game system. The system consists of four main components:
1.  **Game Server** (Python/FastAPI): Manages the game state and simulation.
2.  **Database** (Postgres): Provisioned for persistence (currently optional for core gameplay).
3.  **Dashboard** (Node.js/Express): A web interface to view the game.
4.  **Bots** (Python): Automated clients that play the game.

## Option 1: Quick Start (Docker Compose) - Recommended

The easiest way to run the entire stack is using Docker Compose.

### Prerequisites
*   Docker and Docker Compose installed.

### Steps
1.  Navigate to the project root.
2.  Run the following command:
    ```bash
    docker-compose up --build
    ```
3.  Access the **Dashboard** at [http://localhost:3000](http://localhost:3000).
4.  The game will start automatically once the bots connect.

### Component Logs
To view specific logs:
```bash
docker-compose logs -f server
docker-compose logs -f dashboard
docker-compose logs -f bot_red
docker-compose logs -f bot_blue
```

---

## Option 2: Manual / Local Development

If you wish to run components individually without Docker (e.g., for development or debugging), follow these steps.

### Prerequisites
*   **Python 3.10+** (Recommend using `uv` for dependency management).
*   **Node.js 16+** and `npm`.
*   **PostgreSQL** (running locally or in a container).

### 1. Database Setup
The server expects a Postgres database.
*   **Create a database** named `battle_v2`.
*   **Create a user** (e.g., `admin`) with password (e.g., `password`).
*   *Note: Currently the game engine runs in-memory, but the server checks for DB connection on startup.*

### 2. Server Setup
1.  Navigate to the project root.
2.  Install dependencies:
    ```bash
    uv sync
    # OR if using pip:
    pip install "fastapi[standard]" uvicorn sqlalchemy "psycopg[binary]" pydantic httpx bcrypt pyjwt
    ```
3.  Set environment variables and run:
    ```bash
    # Adjust DATABASE_URL to match your local postgres
    export DATABASE_URL="postgresql+psycopg://admin:password@localhost:5432/battle_v2"
    export CONFIG_DIR="./server/configs"
    
    # Run the server
    uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    The server should now be running at `http://localhost:8000`.

### 3. Dashboard Setup
1.  Navigate to the `dashboard/` directory.
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Set environment variables and start:
    ```bash
    export SERVER_URL="http://localhost:8000"
    npm start
    ```
    The dashboard will be available at `http://localhost:3000`.

### 4. Bot Setup
You need to run two bots (Red and Blue) to play the match. Open two separate terminal windows.

**Bot Red:**
```bash
# In project root
export SERVER_URL="http://localhost:8000"
export MATCH_ID="m_debug_01"
export PLAYER_CONFIG_FILE="./server/configs/p_red.json"

uv run client/client.py
# OR: python client/client.py
```

**Bot Blue:**
```bash
# In project root
export SERVER_URL="http://localhost:8000"
export MATCH_ID="m_debug_01"
export PLAYER_CONFIG_FILE="./server/configs/p_blue.json"

uv run client/client.py
# OR: python client/client.py
```

---

## Game Configuration

### Modifying the Map/Units
The initial game state is defined in `server/main.py` under the `/match/init` or `start_match` endpoints.
*   **Map Radius**: Controlled by `parameters.json` or defaults in `main.py`.
*   **Initial Units**: Hardcoded in `server/engine.py` -> `initialize_dynamic`.

### Bot Logic
Bot logic is located in `client/client.py`. Modify the `_logic` method to change behavior.

## Troubleshooting

*   **Dashboard "Waiting..."**: Ensure the server is running AND the bots have connected. The game only starts when bots join.
*   **Database Error**: If running manually, ensure Postgres is active and the `DATABASE_URL` is correct.
*   **Module Not Found**: Ensure you are running python commands from the **project root**, not inside `server/` or `client/` folders, to ensure `shared` module is resolved correctly (or set `PYTHONPATH=.`).
