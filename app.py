import requests
import time
import threading
import logging
from collections import deque, Counter, defaultdict
from flask import Flask, render_template_string, jsonify

# ==========================================
# TITAN V17 - FAST ASSASSIN (NO SHADOW MOD)
# ==========================================

# --- CONFIGURATION ---
API_URL = "https://wingo1min.onrender.com/api/get_history"
HISTORY_SIZE = 3000       
FETCH_PAGES = 100         # 2000 Data Points
INITIAL_BANKROLL = 100000.0
BASE_BET = 50.0

# --- LOGIC THRESHOLDS ---
MIN_PATTERN_CONF = 0.60   # Deep Search must be at least 60% sure

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger()
app = Flask(__name__)

# ==========================================
# 1. MONEY MANAGER (Martingale)
# ==========================================
class MoneyManager:
    def __init__(self, bankroll):
        self.bankroll = bankroll
        self.level = 1
        self.current_bet_amount = 0.0

    def get_bet(self, is_real_money):
        # Even though we are always real, this safety check remains valid
        if not is_real_money:
            self.current_bet_amount = 0.0
            return 0.0

        # Calculate Martingale Amount (50, 100, 200...)
        calculated_bet = BASE_BET * (2 ** (self.level - 1))
        
        # Safety Cap
        if calculated_bet > self.bankroll: 
            calculated_bet = self.bankroll

        self.current_bet_amount = calculated_bet
        return calculated_bet

    def update_result(self, won):
        if self.current_bet_amount == 0: return 

        if won:
            profit = self.current_bet_amount * 0.98
            self.bankroll += profit
            self.level = 1 
        else:
            self.bankroll -= self.current_bet_amount
            self.level += 1

# ==========================================
# 2. DEEP PATTERN ENGINE
# ==========================================
class DeepPatternEngine:
    def __init__(self):
        self.data = [] 

    def add(self, item):
        self.data.append(item)
        if len(self.data) > HISTORY_SIZE: self.data.pop(0)

    def analyze(self):
        if len(self.data) < 50: return "WAIT", 0.0

        history_str = "".join([x['res'][0] for x in self.data]) 
        
        # Check patterns length 6 down to 3
        for depth in range(6, 2, -1):
            pattern = history_str[-depth:]
            matches = []
            start = 0
            while True:
                idx = history_str.find(pattern, start, len(history_str) - 1)
                if idx == -1: break
                matches.append(history_str[idx + depth])
                start = idx + 1

            if len(matches) < 3: continue 

            counts = Counter(matches) 
            top = counts.most_common(1)[0]
            
            pred = "BIG" if top[0] == 'B' else "SMALL"
            conf = top[1] / len(matches)
            return pred, conf
            
        return "WAIT", 0.0

# ==========================================
# 3. MARKOV ENGINE
# ==========================================
class MarkovEngine:
    def __init__(self):
        self.chains = defaultdict(lambda: {'B': 0, 'S': 0})
        self.raw_history = []

    def train(self, history_items):
        self.chains.clear()
        self.raw_history = [x['res'][0] for x in history_items]
        for i in range(3, len(self.raw_history)):
            prev_3 = "".join(self.raw_history[i-3:i])
            actual = self.raw_history[i]
            self.chains[prev_3][actual] += 1

    def analyze(self):
        if len(self.raw_history) < 5: return "WAIT", 0.0
        
        current_seq = "".join(self.raw_history[-3:])
        stats = self.chains.get(current_seq)
        
        if not stats or (stats['B'] + stats['S'] == 0): return "WAIT", 0.0
            
        total = stats['B'] + stats['S']
        prob_b = stats['B'] / total
        prob_s = stats['S'] / total
        
        return ("BIG", prob_b) if prob_b > prob_s else ("SMALL", prob_s)

# ==========================================
# 4. TITAN SYSTEM (CONTROLLER)
# ==========================================
class TitanSystem:
    def __init__(self):
        self.engine_A = DeepPatternEngine()
        self.engine_B = MarkovEngine()
        self.bank = MoneyManager(INITIAL_BANKROLL)
        
        # State Variables
        self.curr_issue = "Loading..."
        self.prediction = "WAIT"
        self.bet_val = 0.0
        self.mode = "REAL"  # ALWAYS REAL
        self.status = "INIT"
        
        # Streak Trackers
        self.recent_accuracy = deque(maxlen=10) # Last 10 results (True/False)
        self.is_inverted = False # Anti-Trap Switch

        # UI Data
        self.ui_data = {
            "p1": "--", "c1": 0, "p2": "--", "c2": 0,
            "agreement": "NO",
            "mode": "REAL",
            "streak_info": "LIVE TRADING",
            "last_win": "NONE",
            "inverted": "OFF",
            "log": deque(maxlen=15)
        }

    def sync(self):
        self.status = "SYNCING..."
        print(f"📥 Fetching {FETCH_PAGES * 20} Data Points...")
        for p in range(1, FETCH_PAGES + 1): 
            try:
                r = requests.get(API_URL, params={"size": "20", "pageNo": str(p)}, timeout=5)
                if r.status_code == 200:
                    data = r.json()['data']['list']
                    for item in reversed(data): 
                        obj = {'id': str(item['issueNumber']), 'n': int(item['number']), 'res': "BIG" if int(item['number']) >= 5 else "SMALL"}
                        self.engine_A.add(obj)
                if p % 20 == 0: print(f"   ... Page {p}/{FETCH_PAGES}")
            except: pass
            time.sleep(0.05)
            
        self.engine_B.train(self.engine_A.data)
        print("✅ System Ready. LIVE MODE ACTIVE.")
        self.status = "RUNNING"

    def check_inversion(self):
        """Checks if we are being trapped (Accuracy < 20%)"""
        if len(self.recent_accuracy) < 5: return False
        wins = sum(self.recent_accuracy)
        accuracy = wins / len(self.recent_accuracy)
        if accuracy <= 0.20: return True
        return False

    def loop(self):
        self.sync()
        last_id = None
        
        while True:
            try:
                r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=5)
                if r.status_code != 200: time.sleep(1); continue

                latest = r.json()['data']['list'][0]
                curr_id = str(latest['issueNumber'])
                curr_num = int(latest['number'])
                curr_res = "BIG" if curr_num >= 5 else "SMALL"

                if curr_id != last_id:
                    # ===================================
                    # 1. PROCESS LAST RESULT
                    # ===================================
                    res_str = "SKIP"
                    profit_str = "0.00"
                    won_round = False

                    if self.prediction != "WAIT" and last_id:
                        # Check Win/Loss
                        if self.prediction == curr_res:
                            won_round = True
                            res_str = "WIN"
                            self.recent_accuracy.append(1)
                        else:
                            won_round = False
                            res_str = "LOSS"
                            self.recent_accuracy.append(0)

                        # Handle Money (ALWAYS REAL)
                        if won_round:
                            self.bank.update_result(True)
                            profit_str = f"+{self.bet_val*0.98:.2f}"
                        else:
                            self.bank.update_result(False)
                            profit_str = f"-{self.bet_val:.2f}"
                        
                        # Log Result
                        self.ui_data['log'].appendleft({
                            'id': curr_id, 'p': self.prediction, 
                            'r': f"{curr_res} ({curr_num})", 
                            'o': res_str, 'm': profit_str,
                            'mode': "LIVE"
                        })

                    # ===================================
                    # 2. UPDATE ENGINES
                    # ===================================
                    self.engine_A.add({'id': curr_id, 'n': curr_num, 'res': curr_res})
                    self.engine_B.train(self.engine_A.data)

                    # ===================================
                    # 3. PREDICT NEXT
                    # ===================================
                    pred_a, conf_a = self.engine_A.analyze()
                    pred_b, conf_b = self.engine_B.analyze()

                    # Logic: AGREEMENT
                    agreed = False
                    final_pred = "WAIT"
                    
                    if pred_a == pred_b and pred_a != "WAIT":
                        if conf_a >= MIN_PATTERN_CONF:
                            agreed = True
                            final_pred = pred_a
                    
                    # Panic Override
                    if self.bank.level >= 4 and pred_a != "WAIT" and conf_a >= 0.70:
                        agreed = True
                        final_pred = pred_a

                    # ANTI-TRAP INVERSION
                    self.is_inverted = self.check_inversion()
                    if self.is_inverted and final_pred != "WAIT":
                        original = final_pred
                        final_pred = "SMALL" if original == "BIG" else "BIG"
                        print(f"🪤 TRAP DETECTED. INVERTING: {original} -> {final_pred}")

                    # BET CALCULATION (ALWAYS REAL IF AGREED)
                    is_real_bet = agreed
                    self.bet_val = self.bank.get_bet(is_real_bet)
                    
                    self.prediction = final_pred
                    self.curr_issue = str(int(curr_id) + 1)
                    
                    # Update UI Data
                    self.ui_data.update({
                        "p1": pred_a, "c1": f"{conf_a:.0%}",
                        "p2": pred_b, "c2": f"{conf_b:.0%}",
                        "agreement": "YES" if agreed else "NO",
                        "mode": "REAL",
                        "streak_info": "LIVE TRADING",
                        "inverted": "ON" if self.is_inverted else "OFF"
                    })
                    
                    print(f"[LIVE] PRED: {final_pred} | CONF: {conf_a:.0%} | BET: {self.bet_val}")

                    last_id = curr_id

                time.sleep(2)
            except Exception as e:
                print(f"Error: {e}")
                time.sleep(5)

titan = TitanSystem()
threading.Thread(target=titan.loop, daemon=True).start()

# ==========================================
# PRO DASHBOARD UI (HTML/CSS)
# ==========================================
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TITAN V17: LIVE</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #050505; --card: #111; --text: #eee; 
            --accent: #00ff88; --win: #00ff88; --loss: #ff3333; 
            --gold: #ffd700;
        }
        body { background: var(--bg); color: var(--text); font-family: 'JetBrains Mono', monospace; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; border: 1px solid #333; padding: 20px; border-radius: 10px; }
        
        /* HEADER */
        .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #333; padding-bottom: 15px; margin-bottom: 20px; }
        .brand { font-weight: 800; font-size: 1.4rem; color: #fff; }
        .status-dot { height: 10px; width: 10px; background: #666; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .live-dot { background: var(--accent); box-shadow: 0 0 10px var(--accent); }
        
        /* MODE BAR */
        .mode-bar { background: #1a1a1a; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px; border: 1px solid #333; }
        .mode-label { font-size: 0.8rem; color: #888; margin-bottom: 5px; }
        .mode-val { font-size: 1.5rem; font-weight: 800; letter-spacing: 2px; }
        .REAL { color: var(--accent); text-shadow: 0 0 15px var(--accent); }
        
        /* PREDICTION CARD */
        .main-card { background: #0a0a0a; border: 1px solid #333; border-radius: 12px; padding: 30px; text-align: center; margin-bottom: 20px; position: relative; }
        .period { font-size: 1.2rem; margin-bottom: 20px; color: #888; }
        .pred { font-size: 4.5rem; font-weight: 800; margin: 0; line-height: 1; }
        .BIG { color: #ff9900; text-shadow: 0 0 20px rgba(255,153,0,0.5); }
        .SMALL { color: #00ccff; text-shadow: 0 0 20px rgba(0,204,255,0.5); }
        .WAIT { color: #444; }
        .trap-alert { position: absolute; top: 10px; right: 10px; font-size: 0.7rem; color: #ff3333; border: 1px solid #ff3333; padding: 2px 6px; display: none; }

        /* INFO GRID */
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 20px; }
        .info-box { background: #111; padding: 15px; border-radius: 8px; border: 1px solid #222; }
        .label { font-size: 0.7rem; color: #666; text-transform: uppercase; }
        .val { font-size: 1.1rem; font-weight: 700; margin-top: 5px; }
        
        /* HISTORY */
        table { width: 100%; font-size: 0.8rem; border-collapse: collapse; }
        td { padding: 8px 0; border-bottom: 1px solid #222; }
        .res-win { color: var(--win); }
        .res-loss { color: var(--loss); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="brand">TITAN <span style="color:#666">V17-LIVE</span></div>
            <div style="font-size:0.8rem"><span class="status-dot live-dot"></span>ONLINE</div>
        </div>

        <div class="mode-bar">
            <div class="mode-label">CURRENT OPERATION MODE</div>
            <div class="mode-val REAL" id="mode-txt">LIVE</div>
            <div style="font-size:0.8rem; margin-top:5px; color:#555" id="streak-txt">TRADING</div>
        </div>

        <div class="main-card">
            <div class="trap-alert" id="trap-badge">ANTI-TRAP ACTIVE</div>
            <div class="period">PERIOD: <span id="period" style="color:#fff">...</span></div>
            <div class="pred WAIT" id="pred">WAIT</div>
            
            <div class="grid" style="margin-top:30px; margin-bottom:0;">
                <div class="info-box">
                    <div class="label">Deep Search</div>
                    <div class="val" id="eng1">--</div>
                </div>
                <div class="info-box">
                    <div class="label">Markov Trend</div>
                    <div class="val" id="eng2">--</div>
                </div>
            </div>
        </div>

        <div class="grid">
            <div class="info-box">
                <div class="label">Bankroll</div>
                <div class="val" style="color:var(--gold)">$<span id="bank">0</span></div>
            </div>
            <div class="info-box">
                <div class="label">Next Bet</div>
                <div class="val">$<span id="bet">0</span></div>
            </div>
        </div>

        <div style="background:#111; padding:15px; border-radius:8px;">
            <div class="label" style="margin-bottom:10px;">LIVE ACTIVITY LOG</div>
            <table id="log-table"></table>
        </div>
    </div>

    <script>
        function update() {
            fetch('/data').then(r => r.json()).then(d => {
                // Mode Display
                const modeEl = document.getElementById('mode-txt');
                modeEl.innerText = d.mode;
                
                document.getElementById('streak-txt').innerText = d.streak_info;
                
                // Anti-Trap Badge
                const inv = d.inverted || "OFF";
                document.getElementById('trap-badge').style.display = inv === "ON" ? "block" : "none";

                // Prediction
                document.getElementById('period').innerText = d.period;
                const pEl = document.getElementById('pred');
                pEl.innerText = d.pred;
                pEl.className = "pred " + d.pred;

                // Engines
                document.getElementById('eng1').innerText = `${d.d1.p} (${d.d1.c})`;
                document.getElementById('eng2').innerText = `${d.d2.p} (${d.d2.c})`;

                // Money
                document.getElementById('bank').innerText = d.bank;
                document.getElementById('bet').innerText = d.bet;

                // Logs
                let html = '';
                if(d.log.length === 0) {
                    html = '<tr><td colspan="4" style="text-align:center; color:#444; padding:20px;">Waiting for first bet...</td></tr>';
                } else {
                    d.log.forEach(r => {
                        const cls = r.o === 'WIN' ? 'res-win' : (r.o === 'LOSS' ? 'res-loss' : '');
                        html += `<tr>
                            <td>LIVE</td>
                            <td>${r.id.slice(-4)}</td>
                            <td style="font-weight:bold">${r.p}</td>
                            <td class="${cls}">${r.r}</td>
                            <td class="${cls}" style="text-align:right">${r.m}</td>
                        </tr>`;
                    });
                }
                document.getElementById('log-table').innerHTML = html;
            });
        }
        setInterval(update, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def index(): return render_template_string(HTML)

@app.route('/data')
def data():
    return jsonify({
        "period": titan.curr_issue,
        "pred": titan.prediction,
        "d1": {"p": titan.ui_data['p1'], "c": titan.ui_data['c1']},
        "d2": {"p": titan.ui_data['p2'], "c": titan.ui_data['c2']},
        "bank": round(titan.bank.bankroll, 2),
        "bet": titan.bet_val,
        "mode": titan.mode,
        "streak_info": titan.ui_data['streak_info'],
        "inverted": titan.ui_data['inverted'],
        "log": list(titan.ui_data['log'])
    })

if __name__ == '__main__':
    print("---------------------------------------")
    print("TITAN V17 - FAST ASSASSIN LIVE")
    print("OPEN: http://localhost:5555")
    print("---------------------------------------")
    app.run(host='0.0.0.0', port=4444, debug=False)
