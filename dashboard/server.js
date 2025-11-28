const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const app = express();
const PORT = 3000;

// Configuration
const API_URL = process.env.SERVER_URL || 'http://server:8000';

console.log(`Dashboard starting... Proxying API requests to: ${API_URL}`);

// 1. Proxy API requests to Python Backend
// Example: /api/match/m_1/state -> http://server:8000/match/m_1/state
app.use('/api', createProxyMiddleware({
    target: API_URL,
    changeOrigin: true,
    pathRewrite: {
        '^/api': '', // Remove /api prefix when forwarding
    },
    onError: (err, req, res) => {
        console.error("Proxy Error:", err.message);
        res.status(500).send("Proxy Error: Could not connect to Game Server.");
    }
}));

// 2. Serve Static Frontend Files
app.use(express.static('public'));

app.listen(PORT, () => {
    console.log(`Dashboard running at http://localhost:${PORT}`);
});
