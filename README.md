# A battle game

Here is a guide on how to run, view, and debug the battle game. 
The project is set up to run entirely via Docker Compose, which orchestrates the database, server, dashboard, and two bot clients (Red and Blue) automatically.

## Battle Game: Running & Debugging Guide

This guide explains how to spin up the full game stack (Server + DB + Dashboard + 2 Bots) and how to monitor the simulation.

### 1\. Prerequisites

  * **Docker** and **Docker Compose** installed on your machine.

### 2\. How to Run the Game

The repository contains a `docker-compose.yml` file that defines all necessary services. To start the game:

1.  Open your terminal in the root directory of the project (where `docker-compose.yml` is located).
2.  Run the following command to build and start the containers:

<!-- end list -->

```bash
docker-compose up --build
```

**What happens next:**

  * **`db`**: A Postgres database starts.
  * **`server`**: The FastAPI game server starts on port `8000` once the DB is healthy.
  * **`dashboard`**: The Node.js dashboard starts on port `3000`.
  * **`bot_red` & `bot_blue`**: Two Python bots start. They will wait for the server to be ready, then automatically connect to the match `m_debug_01` and begin submitting orders.

### 3\. How to View the Game (Dashboard)

Once the containers are running, you can watch the battle in real-time.

  * Open your web browser and navigate to: **[http://localhost:3000](https://www.google.com/search?q=http://localhost:3000)**

The dashboard connects to the game server (proxied via the Node app) and visualizes the state of match `m_debug_01`. You should see a grid with:

  * **Red Hexes**: Units controlled by the Red Bot.
  * **Blue Hexes**: Units controlled by the Blue Bot.
  * **Tick Counter**: Incrementing every second (1 tick = 1 second).

### 4\. How to Debug (Logs)

To see what is happening "under the hood" or debug issues, you can view the logs for specific services.

**View all logs:**

```bash
docker-compose logs -f
```

**View Server logs (Game Logic & State):**
The server logs will show tick processing, combat events, and incoming orders.

```bash
docker-compose logs -f server
```

**View Bot logs (Decisions & HTTP Errors):**
If a bot isn't moving, check its specific logs to see if it's failing to connect or crashing.

```bash
docker-compose logs -f bot_red
docker-compose logs -f bot_blue
```

**View Dashboard logs (Proxy issues):**

```bash
docker-compose logs -f dashboard
```

### 5\. Modifying the Scenario

Currently, the game creates a hardcoded debug match.

  * **Initial Units:** Defined in `server/main.py` inside the `match_start` endpoint. You will see `UnitState` definitions for `u_red_1` and `u_blue_1`. You can edit this file to add more units or change their positions.
      * *Note: Since the server runs with `--reload` in Docker, saving changes to `server/main.py` will automatically restart the server logic.*
  * **Bot Logic:** Defined in `client/client.py`. You can modify the `_logic` method to change how the bots behave (e.g., make them aggressive or defensive).

### 6\. Troubleshooting

  * **Dashboard shows "Waiting":** This usually means the server hasn't started the match yet. Ensure the `server` container is running and that at least one bot has successfully connected to trigger the `/start` endpoint.
  * **Database Connection Errors:** The `server` waits for the `db` to be healthy, but if it crashes immediately, try running `docker-compose down -v` to clear the database volume and start fresh.
  
