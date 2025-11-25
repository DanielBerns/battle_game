battle_game/
├── shared/                 # LOGIC KERNEL (Used by Server & Client)
│   ├── schemas.py          # Pydantic models (JSON API specs)
│   ├── hex_math.py         # Axial coordinate logic
│   ├── constants.py        # Unit stats, Terrain data
│   └── combat.py           # EHP formulas & Combat resolution
├── server/                 # FASTAPI + POSTGRES
│   ├── main.py             # API Entry points
│   ├── database.py         # SQLAlchemy & Postgres connection
│   ├── models.py           # DB Tables (User, Match, History)
│   ├── auth.py             # Bcrypt & JWT
│   └── engine.py           # The "Master" simulation loop
├── client/                 # HTTPX + SQLITE
│   ├── bot.py              # Main loop & decision logic
│   ├── api_client.py       # HTTPX wrappers
│   └── local_state.py      # SQLite state tracking
└── dashboard/              # NODE.JS + HTML
    ├── server.js           # Express/Node server
    └── public/             # Frontend assets (Canvas/WebGL)
    
