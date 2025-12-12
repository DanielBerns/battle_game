const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

// --- Config ---
const MATCH_ID = 'm_debug_01'; // Default match
const HEX_SIZE = 20; // Radius of hex
const SQRT3 = Math.sqrt(3);
// Layout: Pointy-topped
const HEX_WIDTH = SQRT3 * HEX_SIZE;
const HEX_HEIGHT = 2 * HEX_SIZE;

// --- State ---
let gameState = null;
let camera = { x: window.innerWidth / 2, y: window.innerHeight / 2 };

// --- Main Loop ---
function loop() {
    update();
    draw();
    requestAnimationFrame(loop);
}

// ... existing code ...

// NEW: Add Event Listener
document.getElementById('start-btn').addEventListener('click', async () => {
    try {
        const res = await fetch(`/api/match/${MATCH_ID}/start`, { method: 'POST' });
        if (res.ok) {
            console.log("Game Start Triggered");
        } else {
            console.error("Failed to start game");
        }
    } catch (err) {
        console.error("Error sending start command:", err);
    }
});


async function update() {
    try {
        // Fetch latest state from our Proxy
        const res = await fetch(`/api/match/${MATCH_ID}/state`);
        if (res.ok) {
            const data = await res.json();
            gameState = data;

            // Update HUD
            document.getElementById('tick-display').innerText = data.tick;
            document.getElementById('status-display').innerText = data.game_status;

            // Hide start button if Active
            if (data.game_status === 'ACTIVE') {
                document.getElementById('start-btn').style.display = 'none';
            }

            // Count units (Assuming all visible for observer)
            // Note: In real app, you might need a special 'observer' endpoint to see all
            const units = data.you.units; // Currently only shows what 'you' see
            const red = units.filter(u => u.owner === 'p_red').length;
            const blue = units.filter(u => u.owner === 'p_blue').length;

            document.getElementById('red-count').innerText = red;
            document.getElementById('blue-count').innerText = blue;
        }
    } catch (e) {
        // console.error(e); // Silence errors to avoid log spam if server is down
    }
}

// --- Rendering Logic ---

function draw() {
    // 1. Clear Screen
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (!gameState) return;

    // 2. Draw Grid (Background)
    // Draw a fixed 20x20 grid for context
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    for (let q = -10; q <= 10; q++) {
        for (let r = -10; r <= 10; r++) {
            drawHex(q, r, null);
        }
    }

    // 3. Draw Units
    if (gameState.you && gameState.you.units) {
        gameState.you.units.forEach(unit => {
            let color = unit.owner === 'p_red' ? '#ff4444' : '#4444ff';
            drawHex(unit.q, unit.r, color);

            // Draw Unit Type/HP
            const pixel = hexToPixel(unit.q, unit.r);
            ctx.fillStyle = '#fff';
            ctx.font = '10px Arial';
            ctx.textAlign = 'center';
            ctx.fillText(unit.type[0], pixel.x + camera.x, pixel.y + camera.y + 4);
        });
    }
}

// Convert Axial (q,r) to Pixel (x,y)
function hexToPixel(q, r) {
    const x = HEX_SIZE * (SQRT3 * q + SQRT3/2 * r);
    const y = HEX_SIZE * (3./2 * r);
    return { x, y };
}

function drawHex(q, r, fillColor) {
    const center = hexToPixel(q, r);
    const x = center.x + camera.x;
    const y = center.y + camera.y;

    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
        const angle_deg = 60 * i - 30;
        const angle_rad = Math.PI / 180 * angle_deg;
        ctx.lineTo(x + HEX_SIZE * Math.cos(angle_rad), y + HEX_SIZE * Math.sin(angle_rad));
    }
    ctx.closePath();

    if (fillColor) {
        ctx.fillStyle = fillColor;
        ctx.fill();
    }
    ctx.stroke();
}

// --- Resize Handling ---
window.addEventListener('resize', () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    // Reset camera to center
    camera.x = canvas.width / 2;
    camera.y = canvas.height / 2;
});
// Trigger initial resize
window.dispatchEvent(new Event('resize'));

// Start
loop();
