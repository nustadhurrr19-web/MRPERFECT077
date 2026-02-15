import requests
import time
import threading
import logging
from collections import deque, Counter, defaultdict
from flask import Flask, render_template_string, jsonify

# ==========================================
# TITAN V15 PRO - DASHBOARD EDITION
# ==========================================

# --- CONFIGURATION ---
API_URL = "https://api-iok6.onrender.com/api/get_history"
HISTORY_SIZE = 3000       
INITIAL_BANKROLL = 10000.0
BASE_BET = 50.0

# --- LOGIC THRESHOLDS ---
MIN_PATTERN_CONF = 0.60   # Deep Search must be at least 60% sure
MIN_MARKOV_CONF = 0.50    # Markov must just agree (>50%)

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

    def get_bet(self, confidence, is_agreed):
        # 1. Calculate Martingale Amount (50, 100, 200...)
        calculated_bet = BASE_BET * (2 ** (self.level - 1))
        if calculated_bet > self.bankroll: calculated_bet = self.bankroll

        # 2. DECISION GATE
        # We only place the bet if the engines AGREE.
        if is_agreed and self.bankroll > 0:
            self.current_bet_amount = calculated_bet
            return calculated_bet
        else:
            return 0.0 # SKIP

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
# 4. SYSTEM CONTROLLER
# ==========================================
class TitanSystem:
    def __init__(self):
        self.engine_A = DeepPatternEngine()
        self.engine_B = MarkovEngine()
        self.bank = MoneyManager(INITIAL_BANKROLL)
        
        self.curr_issue = "Loading..."
        self.prediction = "WAIT"
        self.bet_val = 0.0
        self.status = "INIT"
        
        self.ui_data = {
            "p1": "--", "c1": 0, "p2": "--", "c2": 0,
            "agreement": "NO",
            "last_win": "NONE",
            "log": deque(maxlen=10)
        }

    def sync(self):
        self.status = "SYNCING..."
        print("📥 Fetching Data...")
        for p in range(1, 51): 
            try:
                r = requests.get(API_URL, params={"size": "20", "pageNo": str(p)}, timeout=5)
                if r.status_code == 200:
                    data = r.json()['data']['list']
                    for item in reversed(data): 
                        obj = {'id': str(item['issueNumber']), 'n': int(item['number']), 'res': "BIG" if int(item['number']) >= 5 else "SMALL"}
                        self.engine_A.add(obj)
            except: pass
            time.sleep(0.05)
        self.engine_B.train(self.engine_A.data)
        print("✅ System Ready.")
        self.status = "RUNNING"

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
                    # 1. Result Processing
                    res_str = "SKIP"
                    profit_str = "0.00"
                    
                    if self.bet_val > 0 and last_id:
                        if self.prediction == curr_res:
                            self.bank.update_result(True)
                            res_str = "WIN"
                            profit_str = f"+{self.bet_val*0.98:.2f}"
                            self.ui_data['last_win'] = "WIN"
                            print(f"✅ WIN | Bank: {self.bank.bankroll}")
                        else:
                            self.bank.update_result(False)
                            res_str = "LOSS"
                            profit_str = f"-{self.bet_val:.2f}"
                            self.ui_data['last_win'] = "LOSS"
                            print(f"❌ LOSS | Level Up: {self.bank.level}")

                        self.ui_data['log'].appendleft({
                            'id': curr_id, 'p': self.prediction, 
                            'r': f"{curr_res} ({curr_num})", 
                            'o': res_str, 'm': profit_str
                        })

                    # 2. Update & Predict
                    self.engine_A.add({'id': curr_id, 'n': curr_num, 'res': curr_res})
                    self.engine_B.train(self.engine_A.data)

                    pred_a, conf_a = self.engine_A.analyze()
                    pred_b, conf_b = self.engine_B.analyze()

                    # 3. Decision
                    agreed = False
                    final_pred = "WAIT"
                    
                    if pred_a == pred_b and pred_a != "WAIT":
                        if conf_a >= MIN_PATTERN_CONF:
                            agreed = True
                            final_pred = pred_a
                    
                    # Panic Recovery Override (Level 4+)
                    if self.bank.level >= 4 and pred_a != "WAIT" and conf_a >= 0.70:
                        agreed = True
                        final_pred = pred_a

                    self.bet_val = self.bank.get_bet(conf_a, agreed)
                    self.prediction = final_pred
                    self.curr_issue = str(int(curr_id) + 1)
                    
                    self.ui_data.update({
                        "p1": pred_a, "c1": f"{conf_a:.0%}",
                        "p2": pred_b, "c2": f"{conf_b:.0%}",
                        "agreement": "YES" if agreed else "NO"
                    })
                    
                    if agreed:
                        print(f"🔔 BET: {final_pred} ({conf_a:.0%}) | Amt: {self.bet_val}")
                    else:
                        print(f"⚠️ SKIP: Conflict or Low Conf")

                    last_id = curr_id

                time.sleep(2)
            except Exception as e:
                print(e)
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
    <title>TITAN V15 PRO</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f172a; --card: #1e293b; --text: #f8fafc; --muted: #94a3b8;
            --accent: #3b82f6; --win: #22c55e; --loss: #ef4444; --gold: #f59e0b;
            --big: #f97316; --small: #0ea5e9;
        }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; }
        
        /* HEADER */
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .brand { font-weight: 800; font-size: 1.2rem; letter-spacing: -0.02em; }
        .badge { background: #334155; padding: 4px 12px; border-radius: 99px; font-size: 0.75rem; font-weight: 600; }
        
        /* MAIN CARD */
        .card { background: var(--card); border-radius: 16px; padding: 24px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3); border: 1px solid #334155; margin-bottom: 16px; }
        .period-label { color: var(--muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
        .period-val { font-size: 1.5rem; font-weight: 700; color: #fff; margin-bottom: 20px; font-variant-numeric: tabular-nums; }
        
        .pred-container { text-align: center; padding: 30px 0; border-top: 1px solid #334155; border-bottom: 1px solid #334155; }
        .pred-val { font-size: 4rem; font-weight: 900; line-height: 1; letter-spacing: -0.03em; }
        .BIG { color: var(--big); text-shadow: 0 0 30px rgba(249, 115, 22, 0.3); }
        .SMALL { color: var(--small); text-shadow: 0 0 30px rgba(14, 165, 233, 0.3); }
        .WAIT { color: var(--muted); opacity: 0.5; }
        
        /* ENGINES */
        .engines { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 20px; }
        .eng-box { background: #0f172a; padding: 12px; border-radius: 8px; text-align: center; }
        .eng-title { font-size: 0.7rem; color: var(--muted); font-weight: 600; margin-bottom: 4px; }
        .eng-res { font-weight: 700; font-size: 1rem; }
        
        /* STATS GRID */
        .stats { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 16px; }
        .stat-card { background: var(--card); padding: 16px; border-radius: 12px; border: 1px solid #334155; }
        .stat-label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; margin-bottom: 4px; }
        .stat-val { font-size: 1.1rem; font-weight: 700; }
        
        /* HISTORY */
        table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
        th { text-align: left; color: var(--muted); font-weight: 600; padding-bottom: 12px; font-size: 0.75rem; }
        td { padding: 12px 0; border-bottom: 1px solid #334155; }
        .win { color: var(--win); } .loss { color: var(--loss); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="brand">TITAN <span style="color:var(--accent)">V15 PRO</span></div>
            <div class="badge" id="status">CONNECTING...</div>
        </div>

        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:end;">
                <div>
                    <div class="period-label">Current Period</div>
                    <div class="period-val" id="period">Loading...</div>
                </div>
                <div class="badge" id="agree-badge" style="background:#0f172a;">ANALYZING</div>
            </div>
            
            <div class="pred-container">
                <div class="pred-val WAIT" id="pred">WAIT</div>
                <div style="margin-top:10px; font-size:0.9rem; color:var(--muted)" id="bet-info">Waiting for signal...</div>
            </div>

            <div class="engines">
                <div class="eng-box">
                    <div class="eng-title">DEEP SEARCH</div>
                    <div class="eng-res" id="eng1">--</div>
                </div>
                <div class="eng-box">
                    <div class="eng-title">MARKOV TREND</div>
                    <div class="eng-res" id="eng2">--</div>
                </div>
            </div>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Bankroll</div>
                <div class="stat-val" style="color:var(--gold)">$<span id="bank">0</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Next Bet</div>
                <div class="stat-val">$<span id="bet">0</span></div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Level</div>
                <div class="stat-val" id="level">1</div>
            </div>
        </div>

        <div class="card" style="padding: 20px;">
            <div class="period-label" style="margin-bottom:15px;">Recent Activity</div>
            <table>
                <thead>
                    <tr>
                        <th>PERIOD</th>
                        <th>PRED</th>
                        <th>RESULT</th>
                        <th style="text-align:right">PROFIT</th>
                    </tr>
                </thead>
                <tbody id="log-body"></tbody>
            </table>
        </div>
    </div>

    <script>
        function update() {
            fetch('/data').then(r => r.json()).then(d => {
                // Status & Header
                document.getElementById('status').innerText = "LIVE SCANNING";
                document.getElementById('status').style.color = "#22c55e";
                
                // Main Display
                document.getElementById('period').innerText = d.period;
                const pEl = document.getElementById('pred');
                pEl.innerText = d.pred;
                pEl.className = "pred-val " + d.pred;
                
                // Agreement Badge
                const agEl = document.getElementById('agree-badge');
                if(d.d1.agreement === "YES") {
                    agEl.innerText = "ENGINES AGREED";
                    agEl.style.color = "#22c55e";
                } else {
                    agEl.innerText = "CONFLICT / LOW CONF";
                    agEl.style.color = "#94a3b8";
                }

                // Bet Info text
                const infoEl = document.getElementById('bet-info');
                if (d.bet > 0) {
                    infoEl.innerText = `CONFIRMED: Betting $${d.bet} on ${d.pred}`;
                    infoEl.style.color = "#f8fafc";
                } else {
                    infoEl.innerText = "Skipping: Engines do not match or confidence too low.";
                    infoEl.style.color = "#94a3b8";
                }

                // Engines
                document.getElementById('eng1').innerText = `${d.d1.p} (${d.d1.c})`;
                document.getElementById('eng1').style.color = d.d1.p === "BIG" ? "var(--big)" : (d.d1.p === "SMALL" ? "var(--small)" : "#fff");
                
                document.getElementById('eng2').innerText = `${d.d2.p} (${d.d2.c})`;
                document.getElementById('eng2').style.color = d.d2.p === "BIG" ? "var(--big)" : (d.d2.p === "SMALL" ? "var(--small)" : "#fff");

                // Stats
                document.getElementById('bank').innerText = d.bank;
                document.getElementById('bet').innerText = d.bet;
                document.getElementById('level').innerText = d.level;

                // Logs
                let html = '';
                d.log.forEach(r => {
                    const cls = r.o === 'WIN' ? 'win' : (r.o === 'LOSS' ? 'loss' : '');
                    html += `<tr>
                        <td>${r.id.slice(-4)}</td>
                        <td style="font-weight:600">${r.p}</td>
                        <td class="${cls}">${r.r}</td>
                        <td class="${cls}" style="text-align:right">${r.m}</td>
                    </tr>`;
                });
                document.getElementById('log-body').innerHTML = html;
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
        "d1": {"p": titan.ui_data['p1'], "c": titan.ui_data['c1'], "agreement": titan.ui_data['agreement']},
        "d2": {"p": titan.ui_data['p2'], "c": titan.ui_data['c2']},
        "bank": round(titan.bank.bankroll, 2),
        "bet": titan.bet_val,
        "level": titan.bank.level,
        "log": list(titan.ui_data['log'])
    })

if __name__ == '__main__':
    print("---------------------------------------")
    print("TITAN V15 PRO - DASHBOARD LIVE")
    print("GO TO: http://localhost:5050")
    print("---------------------------------------")
    app.run(host='0.0.0.0', port=5551, debug=False)
