import requests
import time
import threading
import os
from collections import Counter
from flask import Flask, render_template_string, jsonify, redirect

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"
PLATFORM_URL = "https://example.com"  # <--- REPLACE WITH YOUR GAME LINK

app = Flask(__name__)

# ==========================================
# 🧠 SMART LOGIC ENGINE (APEX-V2)
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

        pred5, str5 = self.get_pattern_strength(5)
        pred3, str3 = self.get_pattern_strength(3)
        pred4, str4 = self.get_pattern_strength(4)

        if pred5 and pred3 and pred5 != pred3:
            if str5 > 0.90: best_pred, best_strength = pred5, str5
            elif str3 > 0.90: best_pred, best_strength = pred3, str3
            else: return None, "WAITING... (CONFLICT)"
        else:
            best_pred = pred5 if str5 >= str4 else pred4
            best_strength = max(str5, str4, str3)
            
        if not best_pred:
            best_pred = self.history[-1]['s']
            best_strength = 0.5

        sureshot_req = 0.85
        high_req = 0.65
        
        if self.high_loss_streak > 0:
            sureshot_req += 0.05
            high_req += 0.05

        last_val = self.history[-1]['s']
        prev_val = self.history[-2]['s']
        is_trending = (last_val == best_pred)
        is_zigzag = (last_val != prev_val and best_pred != last_val)
        n1, n2 = self.history[-1]['n'], self.history[-2]['n']
        is_symmetric = (n1 + n2 == 9 or n1 == n2)

        if self.high_loss_streak >= 2:
            if best_strength < 0.55: return None, "SKIP (VOLATILE)"
            return best_pred, "RECOVERY"

        if best_strength > sureshot_req and is_symmetric:
            return best_pred, "SURESHOT"
        elif best_strength > high_req and (is_trending or is_zigzag):
            return best_pred, "HIGH BET"
        else:
            return None, "WAITING..."

# ==========================================
# 🔄 WORKER & STATE
# ==========================================
engine = ApexQuantum()
global_state = {
    "period": "Loading...", "prediction": "--", "type": "WAITING...",
    "streak": 0, "last_result": "--", "history_log": [], "win_count": 0, "loss_count": 0
}

def background_worker():
    last_processed_id = None
    active_bet = None
    while True:
        try:
            if not engine.history: engine.sync_data()
            r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=5)
            if r.status_code != 200: continue
            
            latest = r.json()['data']['list'][0]
            curr_id = str(latest['issueNumber'])
            real_num = int(latest['number'])
            real_size = engine.get_size(real_num)

            if curr_id != last_processed_id:
                if active_bet and active_bet['id'] == curr_id:
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
                        global_state["history_log"].insert(0, {"period": curr_id[-4:], "res": real_size, "status": res_status})
                        global_state["history_log"] = global_state["history_log"][:10]

                engine.history.append({'n': real_num, 's': real_size, 'id': curr_id})
                if len(engine.history) > 500: engine.history.pop(0)

                next_id = str(int(curr_id) + 1)
                p_size, p_type = engine.analyze()
                active_bet = {'id': next_id, 'size': p_size, 'type': p_type}
                last_processed_id = curr_id
                
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

t = threading.Thread(target=background_worker)
t.daemon = True
t.start()

# ==========================================
# 🌐 HTML TEMPLATE
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TITAN PRO | CLOUD</title>
    <style>
        :root { --bg: #050505; --panel: #111; --border: #333; --accent: #00f2ff; --win: #00ff88; --loss: #ff0055; --text: #fff; }
        body { background: var(--bg); color: var(--text); font-family: 'Courier New', monospace; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; min-height: 100vh; }
        .dashboard { display: grid; grid-template-columns: 1.5fr 1fr; gap: 20px; max-width: 1200px; width: 100%; }
        .card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 20px; box-shadow: 0 0 20px rgba(0,0,0,0.5); position: relative; overflow: hidden; }
        .card::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, transparent, var(--accent), transparent); }
        .header { width: 100%; max-width: 1200px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
        h1 { margin: 0; font-size: 28px; letter-spacing: 2px; text-transform: uppercase; color: var(--accent); }
        .signal-box { text-align: center; display: flex; flex-direction: column; justify-content: center; min-height: 350px; }
        .period { font-size: 20px; color: #888; margin-bottom: 20px; }
        .pred-type { font-size: 22px; font-weight: bold; padding: 8px 20px; border-radius: 4px; display: inline-block; margin-bottom: 10px; }
        .prediction { font-size: 80px; font-weight: 900; margin: 0; text-transform: uppercase; letter-spacing: 5px; }
        .streak-alert { background: rgba(255, 0, 85, 0.2); color: var(--loss); padding: 10px; border: 1px solid var(--loss); border-radius: 4px; margin-top: 20px; animation: pulse 1s infinite; font-weight: bold; }
        .history-box h3 { margin-top: 0; border-bottom: 1px solid var(--border); padding-bottom: 10px; display: flex; justify-content: space-between; }
        .log-item { display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #222; font-size: 14px; }
        .stats { display: flex; gap: 10px; }
        .stat-pill { padding: 4px 10px; border-radius: 4px; font-size: 14px; font-weight: bold; }
        .btn { background: var(--accent); color: #000; padding: 12px 25px; text-decoration: none; font-weight: bold; border-radius: 4px; text-transform: uppercase; }
        .type-WAITING... { color: #555; border: 1px solid #333; }
        .type-HIGH { background: #ffd700; color: #000; }
        .type-SURESHOT { background: #ff0055; color: #fff; }
        .type-RECOVERY { background: #00ff88; color: #000; }
        .pred-BIG { color: #ff4757; } .pred-SMALL { color: #2ed573; } .pred-None { color: #333; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
        @media (max-width: 768px) { .dashboard { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="header">
        <div><h1>MR PERFECT</h1><div style="font-size: 12px; color: #666;">4 LEVEL MAINATIN</div></div>
        <a href="/go" target="_blank" class="btn">OPEN GAME ↗</a>
    </div>
    <div class="dashboard">
        <div class="card signal-box">
            <div class="period">PERIOD: <span id="period">Scanning...</span></div>
            <div id="type-wrapper"><div id="type-badge" class="pred-type type-WAITING...">WAITING...</div></div>
            <div id="prediction" class="prediction pred-None">--</div>
            <div id="streak-warning" class="streak-alert" style="display: none;">⚠️ RECOVER MODE (LEVEL <span id="streak-lvl">0</span>)</div>
        </div>
        <div class="card history-box">
            <h3>LOG <div class="stats"><span class="stat-pill" style="background:#003300; color:#00ff88">W: <span id="wins">0</span></span><span class="stat-pill" style="background:#330000; color:#ff0055">L: <span id="losses">0</span></span></div></h3>
            <div id="history-list"><div style="padding:20px; text-align:center; color:#444;">...</div></div>
        </div>
    </div>
    <script>
        function update() {
            fetch('/api/status').then(r => r.json()).then(data => {
                document.getElementById('period').innerText = data.period;
                document.getElementById('wins').innerText = data.win_count;
                document.getElementById('losses').innerText = data.loss_count;
                
                let safeType = data.type.split(' ')[0];
                if (data.type.includes("SKIP") || data.type.includes("CONFLICT")) safeType = "WAITING...";
                
                let badge = document.getElementById('type-badge');
                badge.innerText = data.type;
                badge.className = `pred-type type-${safeType}`;
                
                let predDiv = document.getElementById('prediction');
                if(data.type.includes("WAITING") || data.type.includes("SKIP")) {
                    predDiv.innerText = "--"; predDiv.className = "prediction pred-None";
                } else {
                    predDiv.innerText = data.prediction; predDiv.className = `prediction pred-${data.prediction}`;
                }

                let warn = document.getElementById('streak-warning');
                if(data.streak > 0) { warn.style.display = 'block'; document.getElementById('streak-lvl').innerText = data.streak; } 
                else { warn.style.display = 'none'; }

                let histList = document.getElementById('history-list');
                if(data.history_log.length > 0) {
                    histList.innerHTML = data.history_log.map(i => `
                        <div class="log-item"><span style="color:#666">#${i.period}</span><span style="font-weight:bold">${i.res}</span><span style="color: ${i.status === 'WIN' ? '#00ff88' : '#ff0055'}">${i.status}</span></div>
                    `).join('');
                }
            });
        }
        setInterval(update, 1000); update();
    </script>
</body>
</html>
"""

# ==========================================
# 🚀 CLOUD RUNNER
# ==========================================
@app.route('/')
def home(): return render_template_string(HTML_TEMPLATE)

@app.route('/api/status')
def get_status(): return jsonify(global_state)

@app.route('/go')
def go_platform(): return redirect(PLATFORM_URL)

if __name__ == '__main__':
    # ⚠️ THIS IS THE IMPORTANT FIX FOR RENDER ⚠️
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
