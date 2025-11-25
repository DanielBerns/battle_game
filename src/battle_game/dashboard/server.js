const express = require('express');
const app = express();
const { Pool } = require('pg'); // Optional: Connect directly to DB for read-only replays

app.use(express.static('public'));

// Proxy endpoint to Python Server
app.get('/api/match/:id', async (req, res) => {
    // Fetch from FastAPI and forward to frontend
});

app.listen(3000, () => console.log('Dashboard running on 3000'));
