import requests
import time
import threading
import webbrowser
from collections import Counter
from flask import Flask, render_template_string, jsonify, redirect

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"
PLATFORM_URL = "https://example.com"  # <--- REPLACE WITH YOUR ACTUAL GAME LINK
PORT = 5003

app = Flask(__name__)

# ==========================================
# 🧠 SMART LOGIC ENGINE (APEX-V2 UPGRADED)
# ==========================================
class ApexQuantum:
    def __init__(self):
        self.history = []
        self.max_depth = 500
        self.high_loss_streak = 0
        self.wins = 0
        self.losses = 0

    def get_size(self, n): 
        return "BIG" if int(n) >= 5 else "SMALL"

    def sync_data(self):
        try:
            all_data = []
            # Fetch deeper history for better pattern matching
            for p in range(1, 6): 
                r = requests.get(API_URL, params={"size": "20", "pageNo": str(p)}, timeout=5)
                if r.status_code == 200:
                    all_data.extend(r.json().get('data', {}).get('list', []))
            
            all_data.sort(key=lambda x: int(x['issueNumber']))
            self.history = [{'n': int(item['number']), 's': self.get_size(item['number']), 'id': str(item['issueNumber'])} for item in all_data]
            return True
        except:
            return False

    def get_pattern_strength(self, depth):
        """
        Helper function to check specific pattern depths (3, 4, or 5)
        """
        if len(self.history) < depth + 1: return None, 0
        
        last_seq = [x['s'] for x in self.history[-depth:]]
        matches = []
        for i in range(len(self.history) - (depth + 1)):
            if [x['s'] for x in self.history[i : i+depth]] == last_seq:
                matches.append(self.history[i+depth]['s'])
        
        if matches:
            counts = Counter(matches)
            pred_item = counts.most_common(1)[0][0]
            strength = counts[pred_item] / len(matches)
            return pred_item, strength
        return None, 0

    def analyze(self):
        if len(self.history) < 15: return None, "WAITING..."

        # --- 1. MULTI-DEPTH ANALYSIS (Conflict Filter) ---
        # We analyze Long-term (5) vs Short-term (3) patterns
        pred5, str5 = self.get_pattern_strength(5)
        pred3, str3 = self.get_pattern_strength(3)
        pred4, str4 = self.get_pattern_strength(4)

        # Conflict Check: If Long and Short term disagree, we generally SKIP
        if pred5 and pred3 and pred5 != pred3:
            # Only override conflict if one signal is extremely strong (>90%)
            if str5 > 0.90: 
                best_pred, best_strength = pred5, str5
            elif str3 > 0.90: 
                best_pred, best_strength = pred3, str3
            else: 
                return None, "WAITING... (CONFLICT)"
        else:
            # No conflict, pick the strongest signal
            best_pred = pred5 if str5 >= str4 else pred4
            best_strength = max(str5, str4, str3)
            
        if not best_pred: # Fallback
            best_pred = self.history[-1]['s']
            best_strength = 0.5

        # --- 2. DYNAMIC THRESHOLDS (Panic Adjustment) ---
        # If we just lost a bet, we increase the required accuracy by 5-10%
        # This prevents "Tilt Betting" or chasing losses on weak signals.
        sureshot_req = 0.85
        high_req = 0.65
        
        if self.high_loss_streak > 0:
            sureshot_req += 0.05  # Now requires 90%
            high_req += 0.05      # Now requires 70%

        # --- 3. PATTERN FILTERS ---
        last_val = self.history[-1]['s']
        prev_val = self.history[-2]['s']
        
        is_trending = (last_val == best_pred) # Betting on streak (B-B-B)
        is_zigzag = (last_val != prev_val and best_pred != last_val) # Betting on chop (B-S-B)

        # Symmetry Check (Math)
        n1, n2 = self.history[-1]['n'], self.history[-2]['n']
        is_symmetric = (n1 + n2 == 9 or n1 == n2)

        # --- 4. FINAL DECISION TREE ---

        # A. Smart Recovery (Top Priority)
        if self.high_loss_streak >= 2:
            # Safety: If market is too volatile (<55% accuracy), DO NOT recover yet.
            if best_strength < 0.55: 
                return None, "SKIP (VOLATILE)" 
            return best_pred, "RECOVERY"

        # B. Sureshot
        if best_strength > sureshot_req and is_symmetric:
            return best_pred, "SURESHOT"
        
        # C. High Bet (Now supports Trend OR Strong ZigZag)
        elif best_strength > high_req and (is_trending or is_zigzag):
            return best_pred, "HIGH BET"
        
        # D. Low Bet Filter
        else:
            return None, "WAITING..."

# ==========================================
# 🔄 GLOBAL STATE & BACKGROUND WORKER
# ==========================================
engine = ApexQuantum()
global_state = {
    "period": "Loading...",
    "prediction": "--",
    "type": "WAITING...",
    "streak": 0,
    "last_result": "--",
    "history_log": [],
    "win_count": 0,
    "loss_count": 0
}

def background_worker():
    last_processed_id = None
    active_bet = None

    while True:
        try:
            # 1. Sync Data if Empty
            if not engine.history: engine.sync_data()
            
            # 2. Fetch Latest Result
            r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=5)
            if r.status_code != 200: continue
            
            latest = r.json()['data']['list'][0]
            curr_id = str(latest['issueNumber'])
            real_num = int(latest['number'])
            real_size = engine.get_size(real_num)

            # 3. Process Logic
            if curr_id != last_processed_id:
                # Check previous bet outcome
                if active_bet and active_bet['id'] == curr_id:
                    # Ignore WAITING or SKIPPED bets for Win/Loss count
                    if active_bet['type'] not in ["WAITING...", "WAITING... (CONFLICT)", "SKIP (VOLATILE)"]:
                        is_win = (active_bet['size'] == real_size)
                        if is_win:
                            engine.wins += 1
                            engine.high_loss_streak = 0
                            res_status = "WIN"
                        else:
                            engine.losses += 1
                            engine.high_loss_streak += 1
                            res_status = "LOSS"
                        
                        # Add to History Log
                        global_state["history_log"].insert(0, {
                            "period": curr_id[-4:], 
                            "res": real_size, 
                            "status": res_status
                        })
                        # Keep log short (last 10)
                        global_state["history_log"] = global_state["history_log"][:10]

                # Update Engine History
                engine.history.append({'n': real_num, 's': real_size, 'id': curr_id})
                if len(engine.history) > 500: engine.history.pop(0)

                # Predict Next
                next_id = str(int(curr_id) + 1)
                p_size, p_type = engine.analyze()
                
                active_bet = {'id': next_id, 'size': p_size, 'type': p_type}
                last_processed_id = curr_id
                
                # Update Global UI State
                global_state["period"] = next_id
                global_state["prediction"] = p_size if p_size else "--"
                global_state["type"] = p_type
                global_state["streak"] = engine.high_loss_streak
                global_state["last_result"] = f"{real_size} ({curr_id[-4:]})"
                global_state["win_count"] = engine.wins
                global_state["loss_count"] = engine.losses

            time.sleep(2)
        except Exception as e:
            print(f"Worker Error: {e}")
            time.sleep(2)

# Start Background Thread
t = threading.Thread(target=background_worker)
t.daemon = True
t.start()

# ==========================================
# 🌐 FLASK FRONTEND (HTML/CSS/JS)
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
        
        /* Signal Box */
        .signal-box { text-align: center; display: flex; flex-direction: column; justify-content: center; min-height: 350px; }
        .period { font-size: 20px; color: #888; margin-bottom: 20px; }
        
        .pred-type { font-size: 22px; font-weight: bold; padding: 8px 20px; border-radius: 4px; display: inline-block; margin-bottom: 10px; }
        .prediction { font-size: 80px; font-weight: 900; margin: 0; text-transform: uppercase; letter-spacing: 5px; }
        
        .streak-alert { background: rgba(255, 0, 85, 0.2); color: var(--loss); padding: 10px; border: 1px solid var(--loss); border-radius: 4px; margin-top: 20px; animation: pulse 1s infinite; font-weight: bold; }
        
        /* History Box */
        .history-box h3 { margin-top: 0; border-bottom: 1px solid var(--border); padding-bottom: 10px; display: flex; justify-content: space-between; }
        .log-item { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #222; font-size: 14px; }
        .log-item:last-child { border-bottom: none; }
        
        .stats { display: flex; gap: 10px; }
        .stat-pill { padding: 4px 10px; border-radius: 4px; font-size: 14px; font-weight: bold; }
        
        .btn { background: var(--accent); color: #000; padding: 12px 25px; text-decoration: none; font-weight: bold; border-radius: 4px; text-transform: uppercase; transition: 0.3s; }
        .btn:hover { background: #fff; box-shadow: 0 0 15px #fff; }

        /* Dynamic Classes */
        .type-WAITING... { color: #555; border: 1px solid #333; }
        .type-HIGH { background: #ffd700; color: #000; box-shadow: 0 0 20px rgba(255, 215, 0, 0.4); }
        .type-SURESHOT { background: #ff0055; color: #fff; box-shadow: 0 0 30px rgba(255, 0, 85, 0.6); }
        .type-RECOVERY { background: #00ff88; color: #000; box-shadow: 0 0 30px rgba(0, 255, 136, 0.6); }
        
        .pred-BIG { color: #ff4757; text-shadow: 0 0 20px rgba(255, 71, 87, 0.5); }
        .pred-SMALL { color: #2ed573; text-shadow: 0 0 20px rgba(46, 213, 115, 0.5); }
        .pred-None { color: #333; text-shadow: none; }

        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        @media (max-width: 768px) { .dashboard { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>MR PERFECT </h1>
            <div style="font-size: 20px; color: #666;">4 LEVEL MAINTAIN </div>
        </div>
        <a href="/go" target="https://t.me/+UokUj32JokUwMzU1" class="btn">TELEGRAM ↗</a>
    </div>

    <div class="dashboard">
        <div class="card signal-box">
            <div class="period">PERIOD: <span id="period">Scanning...</span></div>
            
            <div id="type-wrapper">
                <div id="type-badge" class="pred-type type-WAITING...">WAITING...</div>
            </div>
            
            <div id="prediction" class="prediction pred-None">--</div>
            
            <div id="streak-warning" class="streak-alert" style="display: none;">
                ⚠️ STOP & RECOVER MODE (LEVEL <span id="streak-lvl">0</span>)
            </div>
        </div>

        <div class="card history-box">
            <h3>
                ACTIVITY LOG
                <div class="stats">
                    <span class="stat-pill" style="background:#003300; color:#00ff88">W: <span id="wins">0</span></span>
                    <span class="stat-pill" style="background:#330000; color:#ff0055">L: <span id="losses">0</span></span>
                </div>
            </h3>
            <div id="history-list">
                <div style="padding:20px; text-align:center; color:#444;">No active bets yet...</div>
            </div>
        </div>
    </div>

    <script>
        function update() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('period').innerText = data.period;
                    document.getElementById('wins').innerText = data.win_count;
                    document.getElementById('losses').innerText = data.loss_count;
                    
                    const typeBadge = document.getElementById('type-badge');
                    const predDiv = document.getElementById('prediction');
                    
                    // Handle Badge Styling
                    let safeType = data.type.split(' ')[0]; // Extract "HIGH" from "HIGH BET"
                    if (data.type.includes("SKIP")) safeType = "WAITING...";
                    if (data.type.includes("CONFLICT")) safeType = "WAITING...";
                    
                    typeBadge.innerText = data.type;
                    typeBadge.className = `pred-type type-${safeType}`;
                    
                    // Handle Prediction Display
                    if(data.type.includes("WAITING") || data.type.includes("SKIP")) {
                        predDiv.innerText = "--";
                        predDiv.className = "prediction pred-None";
                    } else {
                        predDiv.innerText = data.prediction;
                        predDiv.className = `prediction pred-${data.prediction}`;
                    }

                    // Recovery Alert
                    const warn = document.getElementById('streak-warning');
                    if(data.streak > 0) {
                        warn.style.display = 'block';
                        document.getElementById('streak-lvl').innerText = data.streak;
                    } else {
                        warn.style.display = 'none';
                    }

                    // History
                    const histList = document.getElementById('history-list');
                    if(data.history_log.length > 0) {
                        histList.innerHTML = data.history_log.map(item => `
                            <div class="log-item">
                                <span style="color:#666">#${item.period}</span>
                                <span style="font-weight:bold">${item.res}</span>
                                <span style="color: ${item.status === 'WIN' ? '#00ff88' : '#ff0055'}">${item.status}</span>
                            </div>
                        `).join('');
                    }
                });
        }
        setInterval(update, 1000); // 1 Second refresh rate
        update();
    </script>
</body>
</html>
"""

# ==========================================
# 🚀 FLASK ROUTES
# ==========================================
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def get_status():
    return jsonify(global_state)

@app.route('/go')
def go_platform():
    return redirect(PLATFORM_URL)

if __name__ == '__main__':
    print(f"🔥 TITAN ULTIMATE SERVER STARTED: http://localhost:{PORT}")
    print("⚠️  MINIMIZE THIS WINDOW, DO NOT CLOSE IT.")
    webbrowser.open(f"http://localhost:{PORT}")
    app.run(port=PORT, debug=False)
