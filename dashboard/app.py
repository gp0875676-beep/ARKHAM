# dashboard/app.py — FastAPI app serving dashboard + JSON APIs.
"""Read-only dashboard. Uses vanilla JS frontend pulling from /api endpoints."""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from db.models import AlertRepo, WalletRepo, ClusterRepo
from config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)


def create_app(lifespan=None) -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="ARC Reactor Dashboard")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/alerts")
    async def get_alerts():
        repo = AlertRepo()
        alerts = await repo.recent(50)
        # Convert asyncpg Records to dicts
        return [dict(a) for a in alerts]

    @app.get("/api/wallets")
    async def get_wallets():
        settings = get_settings()
        chains = settings.enabled_chains
        out = {}
        repo = WalletRepo()
        for c in chains:
            out[c] = await repo.get_tracked(c)
        return out

    @app.get("/api/clusters")
    async def get_clusters():
        repo = ClusterRepo()
        clusters = await repo.get_all_clusters()
        return [dict(c) for c in clusters]

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML_DASHBOARD

    return app


HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ARC Reactor Dashboard</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: auto; }
        h1 { color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 10px; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card { background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 20px; }
        h2 { color: #8b949e; margin-top: 0; font-size: 1.2rem; text-transform: uppercase; }
        .item { background: #0d1117; padding: 10px; margin-bottom: 10px; border-radius: 4px; border-left: 3px solid #f78166; word-wrap: break-word; }
        .item .meta { font-size: 0.8rem; color: #8b949e; margin-bottom: 5px; }
        .item .msg { font-family: monospace; white-space: pre-wrap; color: #e6edf3; }
        .wallet-list { list-style: none; padding: 0; }
        .wallet-list li { background: #21262d; padding: 8px; border-radius: 4px; margin-bottom: 5px; font-family: monospace; font-size: 0.9rem; word-break: break-all; }
        .badge { background: #238636; color: white; padding: 2px 6px; border-radius: 12px; font-size: 0.7rem; margin-left: 10px; vertical-align: middle; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🐋 ARC Reactor Dashboard</h1>
        <div class="grid">
            <div class="card" style="grid-column: span 2;">
                <h2>Recent Alerts (Live)</h2>
                <div id="alerts-list">Loading...</div>
            </div>
            <div class="card">
                <h2>Tracked Wallets</h2>
                <div id="wallets-list">Loading...</div>
            </div>
            <div class="card">
                <h2>Wallet Clusters</h2>
                <div id="clusters-list">Loading...</div>
            </div>
        </div>
    </div>
    <script>
        async function fetchData() {
            try {
                const [alertsRes, walletsRes, clustersRes] = await Promise.all([
                    fetch('/api/alerts'),
                    fetch('/api/wallets'),
                    fetch('/api/clusters')
                ]);

                const alerts = await alertsRes.json();
                const wallets = await walletsRes.json();
                const clusters = await clustersRes.json();

                // Render Alerts
                const alertsDiv = document.getElementById('alerts-list');
                if (!alerts.length) {
                    alertsDiv.innerHTML = '<p>No alerts yet. Waiting for whale activity...</p>';
                } else {
                    alertsDiv.innerHTML = alerts.map(a => `
                        <div class="item">
                            <div class="meta">
                                ${new Date(a.created_at).toLocaleString()} | 
                                <span style="color:#58a6ff">Score: ${a.score}/100</span> | 
                                <span style="color:#f78166">${a.chain.toUpperCase()}</span>
                            </div>
                            <div class="msg">${a.message.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
                        </div>
                    `).join('');
                }

                // Render Wallets
                const walletsDiv = document.getElementById('wallets-list');
                let wHtml = '';
                for (const [chain, list] of Object.entries(wallets)) {
                    wHtml += `<h3 style="color:#58a6ff; font-size:1rem;">${chain.toUpperCase()}</h3><ul class="wallet-list">`;
                    list.forEach(w => wHtml += `<li>${w}</li>`);
                    wHtml += '</ul>';
                }
                walletsDiv.innerHTML = wHtml || '<p>No wallets configured.</p>';

                // Render Clusters
                const clustersDiv = document.getElementById('clusters-list');
                if (!clusters.length) {
                    clustersDiv.innerHTML = '<p>No clusters detected yet.</p>';
                } else {
                    clustersDiv.innerHTML = clusters.map(c => `
                        <div class="item" style="border-left-color:#58a6ff">
                            <div class="meta">Cluster ID: ${c.id} <span class="badge">${c.member_count} wallets</span></div>
                            <div class="msg">${c.wallets.join('<br>')}</div>
                        </div>
                    `).join('');
                }
            } catch (e) {
                console.error("Failed to fetch dashboard data:", e);
            }
        }
        fetchData();
        setInterval(fetchData, 15000); // Auto-refresh every 15 seconds
    </script>
</body>
</html>
"""
