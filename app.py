import requests
import time
import threading
import os
import sqlite3
from collections import Counter
from datetime import datetime
from flask import Flask, render_template_string, jsonify, redirect

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"
PLATFORM_URL = "https://example.com" 
DB_FILE = "titan_data.db"  # Persistent file for Render

app = Flask(__name__)

# ==========================================
# 💾 DATABASE MANAGER (FIXES "0 RECORDS" BUG)
# ==========================================
class TitanDB:
    def __init__(self):
        # Allow multi-thread access for Gunicorn
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                issue TEXT PRIMARY KEY, 
                number INTEGER, 
                size TEXT, 
                timestamp TEXT
            )
        ''')
        self.conn.commit()

    def sync_data(self):
        """Fetches 300 records to fill the database instantly."""
        try:
            # Request 300 items at once
            r = requests.get(API_URL, params={"size": "300", "pageNo": "1"}, timeout=10)
            if r.status_code == 200:
                data = r.json().get('data', {}).get('list', [])
                bulk_insert = []
                for item in data:
                    num = int(item['number'])
                    size = "BIG" if num >= 5 else "SMALL"
                    issue = str(item['issueNumber'])
                    now = str(datetime.now())
                    bulk_insert.append((issue, num, size, now))
                
                # Insert or Ignore duplicates
                self.cursor.executemany("INSERT OR IGNORE INTO results VALUES (?,?,?,?)", bulk_insert)
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Sync Error: {e}")
        return False

    def get_history(self, limit=1000):
        """Returns history sorted by Issue Number (Oldest -> Newest) for analysis."""
        self.cursor.execute(f"SELECT issue, number, size FROM results ORDER BY issue DESC LIMIT {limit}")
        rows = self.cursor.fetchall()
        # Convert to list of dicts and reverse so it is Oldest -> Newest
        clean_data = [{"id": r[0], "n": r[1], "s": r[2]} for r in rows]
        return list(reversed(clean_data))

db = TitanDB()

# ==========================================
# 🧠 SMART LOGIC ENGINE (WITH VIOLET SKIP)
# ==========================================
class ApexQuantum:
    def __init__(self):
        self.high_loss_streak = 0
        self.wins = 0
        self.losses = 0

    def get_pattern_strength(self, history, depth):
        if len(history) < depth + 1: return None, 0
        
        last_seq = [x['s'] for x in history[-depth:]]
        matches = []
        
        # Scan history for this sequence
        for i in range(len(history) - (depth + 1)):
            if [x['s'] for x in history[i : i+depth]] == last_seq:
                matches.append(history[i+depth]['s'])
        
        if matches:
            counts = Counter(matches)
            pred_item = counts.most_common(1)[0][0]
            strength = counts[pred_item] / len(matches)
            return pred_item, strength
        return None, 0

    def analyze(self):
        history = db.get_history(500)
        if len(history) < 15: return None, "SYNCING..."

        # --- 1. VIOLET / VOLATILE FILTER (NEW) ---
        # Check the VERY LAST result. If it was 0 or 5 (Violet), we flag it.
        last_num = history[-1]['n']
        is_violet_volatile = (last_num == 0 or last_num == 5)

        # --- 2. PATTERN ANALYSIS ---
        pred5, str5 = self.get_pattern_strength(history, 5)
        pred3, str3 = self.get_pattern_strength(history, 3)
        pred4, str4 = self.get_pattern_strength(history, 4)

        if pred5 and pred3 and pred5 != pred3:
            if str5 > 0.90: best_pred, best_strength = pred5, str5
            elif str3 > 0.90: best_pred, best_strength = pred3, str3
            else: return None, "WAITING... (CONFLICT)"
        else:
            best_pred = pred5 if str5 >= str4 else pred4
            best_strength = max(str5, str4, str3)
            
        if not best_pred:
            best_pred = history[-1]['s']
            best_strength = 0.5

        # --- 3. DECISION LOGIC ---
        sureshot_req = 0.85
        
        # MATH SYMMETRY
        n1, n2 = history[-1]['n'], history[-2]['n']
        is_symmetric = (n1 + n2 == 9 or n1 == n2)
        
        # LOGIC: If Violet Volatile, ONLY allow SURESHOTS
        if is_violet_volatile:
            if best_strength > 0.90 and is_symmetric:
                return best_pred, "SURESHOT (VIOLET SAFE)"
            else:
                return None, "SKIP (0/5 DETECTED)"

        # Normal Logic
        if self.high_loss_streak >= 2:
            return best_pred, "RECOVERY"

        if best_strength > sureshot_req and is_symmetric:
            return best_pred, "SURESHOT"
        elif best_strength > 0.65:
            return best_pred, "HIGH BET"
        else:
            return None, "WAITING..."

engine = ApexQuantum()

# ==========================================
# 🔄 BACKGROUND WORKER
# ==========================================
global_state = {
    "period": "Loading...", "prediction": "--", "type": "WAITING...",
    "streak": 0, "last_result": "--", "history_log": [],
    "win_count": 0, "loss_count": 0, "db_count": 0
}

def background_worker():
    last_processed_id = None
    active_bet = None

    while True:
        try:
            # Sync Database
            db.sync_data()
            
            # Get Latest Data for Processing
            history = db.get_history(2) # Just need last few for result checking
            if not history: 
                time.sleep(2)
                continue

            latest = history[-1]
            curr_id = latest['id']
            real_size = latest['s']
            
            # Update Global DB Count
            global_state['db_count'] = len(db.get_history(2000))

            if curr_id != last_processed_id:
                # CHECK RESULT
                if active_bet and active_bet['id'] == curr_id:
                    # Don't count SKIPS or WAITS
                    if "SKIP" not in active_bet['type'] and "WAITING" not in active_bet['type']:
                        is_win = (active_bet['size'] == real_size)
                        if is_win:
                            engine.wins += 1
                            engine.high_loss_streak = 0
                            res_status = "WIN"
                        else:
                            engine.losses += 1
                            engine.high_loss_streak += 1
                            res_status = "LOSS"
                        
                        global_state["history_log"].insert(0, {
                            "period": curr_id[-4:], "res": real_size, "status": res_status
                        })
                        global_state["history_log"] = global_state["history_log"][:10]

                # PREDICT NEXT
                next_id = str(int(curr_id) + 1)
                p_size, p_type = engine.analyze()
                
                active_bet = {'id': next_id, 'size': p_size, 'type': p_type}
                last_processed_id = curr_id
                
                global_state.update({
                    "period": next_id,
                    "prediction": p_size if p_size else "--",
                    "type": p_type,
                    "streak": engine.high_loss_streak,
                    "last_result": f"{real_size} ({curr_id[-4:]})",
                    "win_count": engine.wins,
                    "loss_count": engine.losses
                })
            
            time.sleep(2)
        except Exception as e:
            print(f"Worker Error: {e}")
            time.sleep(5)

# Start Background Thread
t = threading.Thread(target=background_worker, daemon=True)
t.start()

# ==========================================
# 🌐 FRONTEND (TITAN PRO UI)
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TITAN PRO | ULTIMATE</title>
    <style>
        :root { --bg: #050505; --panel: #111; --border: #333; --accent: #00f2ff; --win: #00ff88; --loss: #ff0055; --text: #fff; }
        body { background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; min-height: 100vh; }
        .dashboard { display: grid; grid-template-columns: 1.5fr 1fr; gap: 20px; max-width: 1200px; width: 100%; }
        .card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 20px; box-shadow: 0 0 20px rgba(0,0,0,0.5); position: relative; overflow: hidden; }
        .card::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, transparent, var(--accent), transparent); }
        .header { width: 100%; max-width: 1200px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
        h1 { margin: 0; font-size: 28px; letter-spacing: 2px; text-transform: uppercase; color: var(--accent); text-shadow: 0 0 10px var(--accent); }
        .signal-box { text-align: center; display: flex; flex-direction: column; justify-content: center; min-height: 350px; }
        .period { font-size: 20px; color: #888; margin-bottom: 20px; }
        .pred-type { font-size: 22px; font-weight: bold; padding: 8px 20px; border-radius: 4px; display: inline-block; margin-bottom: 10px; }
        .prediction { font-size: 80px; font-weight: 900; margin: 0; text-transform: uppercase; letter-spacing: 5px; }
        .data-counter { font-size: 11px; color: #444; margin-top: 15px; border-top: 1px solid #222; padding-top: 10px; }
        .type-WAITING... { color: #555; border: 1px solid #333; }
        .type-HIGH { background: #ffd700; color: #000; }
        .type-SURESHOT { background: #ff0055; color: #fff; }
        .type-RECOVERY { background: #00ff88; color: #000; }
        .type-SKIP { color: #cc00ff; border: 1px solid #cc00ff; }
        .pred-BIG { color: #ff4757; }
        .pred-SMALL { color: #2ed573; }
        .log-item { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #222; font-size: 14px; }
        .btn { background: var(--accent); color: #000; padding: 10px 20px; text-decoration: none; font-weight: bold; border-radius: 4px; }
        @media (max-width: 768px) { .dashboard { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <div><h1>TITAN PRO</h1><div style="font-size: 12px; color: #666;">SERVER ACTIVE</div></div>
        <a href="/go" class="btn">PLATFORM ↗</a>
    </div>
    <div class="dashboard">
        <div class="card signal-box">
            <div class="period">PERIOD: <span id="period">Scanning...</span></div>
            <div id="type-badge" class="pred-type type-WAITING...">WAITING...</div>
            <div id="prediction" class="prediction">--</div>
            <div class="data-counter">DATABASE: <span id="db-count">0</span> RECORDS</div>
        </div>
        <div class="card">
            <h3>LOGS (W:<span id="wins">0</span> L:<span id="losses">0</span>)</h3>
            <div id="history-list"></div>
        </div>
    </div>
    <script>
        function update() {
            fetch('/api/status').then(r => r.json()).then(data => {
                document.getElementById('period').innerText = data.period;
                document.getElementById('wins').innerText = data.win_count;
                document.getElementById('losses').innerText = data.loss_count;
                document.getElementById('db-count').innerText = data.db_count;
                
                const predDiv = document.getElementById('prediction');
                const badge = document.getElementById('type-badge');
                
                if (data.type.includes("WAITING") || data.type.includes("SKIP") || data.type.includes("SYNC")) {
                    predDiv.innerText = "--"; 
                    predDiv.className = "prediction";
                } else {
                    predDiv.innerText = data.prediction;
                    predDiv.className = `prediction pred-${data.prediction}`;
                }
                
                badge.innerText = data.type;
                let cleanType = data.type.split(' ')[0]; // Extract SKIP from "SKIP (VIOLET)"
                badge.className = `pred-type type-${cleanType}`;
                
                const list = document.getElementById('history-list');
                if(data.history_log.length > 0) {
                    list.innerHTML = data.history_log.map(item => `
                        <div class="log-item"><span>#${item.period}</span><strong>${item.res}</strong><span style="color:${item.status === 'WIN' ? '#00ff88' : '#ff0055'}">${item.status}</span></div>
                    `).join('');
                }
            });
        }
        setInterval(update, 2000);
        update();
    </script>
</body>
</html>
"""

# ==========================================
# 🚀 FLASK ROUTES
# ==========================================
@app.route('/')
def home(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def get_status(): return jsonify(global_state)

@app.route('/go')
def go_platform(): return redirect(PLATFORM_URL)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5003))
    app.run(host='0.0.0.0', port=port)
