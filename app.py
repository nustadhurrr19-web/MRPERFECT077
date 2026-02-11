import requests
import time
import threading
import os
import json
from collections import Counter, defaultdict
from flask import Flask, render_template_string, jsonify

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history" 
app = Flask(__name__)

# ==========================================
# 🧠 TITAN V4 HYBRID BRAIN
# ==========================================
class TitanBrain:
    def __init__(self):
        self.history = []
        
        # --- Stats ---
        self.wins = 0
        self.losses = 0
        self.current_win_streak = 0
        self.current_loss_streak = 0
        self.max_win_streak = 0
        self.max_loss_streak = 0
        
        # --- State Logic ---
        self.level = 1  # 1, 2, or 3
        self.state = "NORMAL"  # NORMAL, GHOST_RECOVERY, CHAOS_PAUSE
        self.ghost_turns_left = 0
        self.last_prediction = None
        
        # --- MATH ENGINE (Markov Chain Order-3) ---
        # Stores patterns like (BIG, SMALL, BIG) -> Next?
        self.markov_table = defaultdict(lambda: {'BIG': 0, 'SMALL': 0})

        # --- PATTERN ENGINE (The Full 17) ---
        self.patterns = {
            "11111": 1, "00000": 0, # Dragon
            "10101": 0, "01010": 1, # ZigZag
            "11001": 0, "00110": 1, # AABB Break
            "11100": 0, "00011": 1, # 3-2 Split
            "10010": 1, "01101": 0, # Sandwich
            "11011": 0, "00100": 1, # Double Pair
            "11101": 0, "00010": 1, # 3-1 Break
            "10001": 0, "01110": 1, # Mirror
            "12121": 0, "11211": 1, # Jump / Asym
            "11110": 0, "00001": 1, # Dragon Cut
            "10000": 1, "01111": 0, # Reverse Cut
            "10111": 0, "01000": 1  # 1-3-1
        }

    def get_size(self, n): return 1 if int(n) >= 5 else 0
    def get_size_str(self, s): return "BIG" if s == 1 else "SMALL"

    def sync_data(self):
        try:
            all_data = []
            # Deep fetch for Markov training
            for p in range(1, 40): 
                r = requests.get(API_URL, params={"size": "20", "pageNo": str(p)}, timeout=4)
                if r.status_code == 200:
                    d = r.json().get('data', {}).get('list', [])
                    if not d: break
                    all_data.extend(d)
            all_data.sort(key=lambda x: int(x['issueNumber']))
            
            self.history = [{'n': int(i['number']), 's': self.get_size(i['number']), 'id': str(i['issueNumber'])} for i in all_data]
            
            # TRAIN MATH ENGINE
            self.train_markov()
            return True
        except: return False

    def train_markov(self):
        """Builds the probability map from history (From Mr. Perfect)"""
        self.markov_table.clear()
        for i in range(3, len(self.history)):
            # Pattern: Last 3 results
            pat = (self.history[i-3]['s'], self.history[i-2]['s'], self.history[i-1]['s'])
            res = self.history[i]['s'] # 0 or 1
            res_str = 'BIG' if res == 1 else 'SMALL'
            self.markov_table[pat][res_str] += 1

    def check_volatility(self):
        """Safety Check from Mr. Perfect: Is market too chaotic?"""
        if len(self.history) < 15: return False
        
        # Count flips in last 12 rounds
        flips = 0
        recent = self.history[-12:]
        for i in range(1, len(recent)):
            if recent[i]['s'] != recent[i-1]['s']:
                flips += 1
        
        # If > 8 flips in 12 rounds, it's Choppy/Dangerous
        return flips >= 8

    def get_math_prediction(self):
        """Returns Markov Prediction"""
        if len(self.history) < 10: return None, 0.0
        
        # Get last 3
        last3 = (self.history[-3]['s'], self.history[-2]['s'], self.history[-1]['s'])
        
        if last3 in self.markov_table:
            stats = self.markov_table[last3]
            total = stats['BIG'] + stats['SMALL']
            if total > 0:
                if stats['BIG'] > stats['SMALL']:
                    return 1, stats['BIG'] / total
                elif stats['SMALL'] > stats['BIG']:
                    return 0, stats['SMALL'] / total
        
        return None, 0.0

    def get_pattern_prediction(self):
        """Returns 17-Pattern Prediction"""
        if len(self.history) < 6: return None
        seq = "".join([str(x['s']) for x in self.history[-5:]])
        
        # 1. Dictionary Check
        if seq in self.patterns: return self.patterns[seq]
        
        # 2. Basic Logic
        if seq == "11111": return 1 # Dragon
        if seq == "00000": return 0
        
        return None

    def analyze(self):
        # 1. SAFETY CHECK
        if self.check_volatility():
            return None, "⚠️ MARKET CHAOS (PAUSED)", False

        # 2. GATHER INTEL
        pat_pred = self.get_pattern_prediction()
        math_pred, math_conf = self.get_math_prediction()
        
        final_pred = None
        algo_type = "WAITING"
        
        # 3. LEVEL LOGIC
        if self.level == 1:
            # LEVEL 1: Standard (Any good signal)
            if pat_pred is not None:
                final_pred = pat_pred
                algo_type = "LVL 1 | PATTERN"
            elif math_pred is not None and math_conf > 0.55:
                final_pred = math_pred
                algo_type = f"LVL 1 | MATH ({int(math_conf*100)}%)"
                
        elif self.level == 2:
            # LEVEL 2: Strong (Better signal needed)
            if pat_pred is not None and math_pred is not None and pat_pred == math_pred:
                final_pred = pat_pred
                algo_type = "LVL 2 | HYBRID AGREEMENT"
            elif math_pred is not None and math_conf > 0.70:
                final_pred = math_pred
                algo_type = f"LVL 2 | MATH STRONG"
            elif pat_pred is not None:
                final_pred = pat_pred
                algo_type = "LVL 2 | PATTERN LOCK"
                
        elif self.level == 3:
            # LEVEL 3: PERFECT (Consensus Only)
            if pat_pred is not None and math_pred is not None and pat_pred == math_pred:
                final_pred = pat_pred
                algo_type = "🔥 LVL 3 | PERFECT MATCH"
            else:
                return None, "⛔ LVL 3 WAITING FOR PERFECT...", False

        return final_pred, algo_type, True

# ==========================================
# 🔄 WORKER THREAD
# ==========================================
engine = TitanBrain()
global_state = {
    "period": "Loading...", "prediction": "--", "type": "WAITING...",
    "wins": 0, "losses": 0, "level": 1,
    "max_win": 0, "max_loss": 0, "mode": "NORMAL",
    "history": []
}

def background_worker():
    last_pid = None
    while True:
        try:
            if not engine.history: engine.sync_data()
            
            r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=5)
            if r.status_code != 200: 
                time.sleep(3)
                continue
                
            data = r.json()['data']['list'][0]
            curr_pid = str(data['issueNumber'])
            real_res = engine.get_size(data['number']) 
            
            if curr_pid != last_pid:
                # --- RESULT PROCESSING ---
                is_win = False
                status_txt = "SKIP"
                
                # Update Math Engine Real-Time
                engine.history.append({'n': int(data['number']), 's': real_res, 'id': curr_pid})
                engine.train_markov()
                if len(engine.history) > 1000: engine.history.pop(0)

                # Check Bet
                if engine.last_prediction is not None:
                    is_win = (engine.last_prediction == real_res)
                    
                    if engine.state == "NORMAL":
                        if is_win:
                            engine.wins += 1
                            engine.current_win_streak += 1
                            engine.current_loss_streak = 0
                            if engine.current_win_streak > engine.max_win_streak:
                                engine.max_win_streak = engine.current_win_streak
                            
                            # WIN -> RESET TO LEVEL 1
                            engine.level = 1 
                            status_txt = "WIN"
                        else:
                            engine.losses += 1
                            engine.current_loss_streak += 1
                            engine.current_win_streak = 0
                            if engine.current_loss_streak > engine.max_loss_streak:
                                engine.max_loss_streak = engine.current_loss_streak
                            
                            status_txt = "LOSS"
                            
                            # LOSS -> ESCALATE LEVEL
                            if engine.level < 3:
                                engine.level += 1
                            else:
                                # Level 3 Lost -> GHOST MODE
                                engine.state = "GHOST_RECOVERY"
                                engine.ghost_turns_left = 3
                                engine.level = 1 
                                status_txt = "LOSS (GHOST TRIGGER)"

                    elif engine.state == "GHOST_RECOVERY":
                        engine.ghost_turns_left -= 1
                        status_txt = f"GHOST {'WIN' if is_win else 'LOSS'}"
                        if engine.ghost_turns_left <= 0:
                            engine.state = "NORMAL"
                            engine.level = 1

                # Log History
                mode_tag = "REAL" if engine.state == "NORMAL" and "GHOST" not in status_txt else "GHOST"
                global_state["history"].insert(0, {
                    "p": curr_pid[-4:], 
                    "r": engine.get_size_str(real_res), 
                    "s": status_txt,
                    "m": mode_tag
                })
                global_state["history"] = global_state["history"][:20]

                # --- PREDICT NEXT ---
                pred, algo, is_valid = engine.analyze()
                
                # Chaos Handling
                if "CHAOS" in algo:
                    engine.last_prediction = None
                    d_pred = "PAUSE"
                    d_type = algo
                else:
                    engine.last_prediction = pred
                    
                    if pred is not None:
                        if engine.state == "NORMAL":
                            d_pred = engine.get_size_str(pred)
                            d_type = algo
                        else:
                            d_pred = "SKIP"
                            d_type = f"🛡️ GHOST ({engine.ghost_turns_left})"
                    else:
                        d_pred = "--"
                        d_type = algo

                global_state.update({
                    "period": str(int(curr_pid) + 1),
                    "prediction": d_pred,
                    "type": d_type,
                    "wins": engine.wins,
                    "losses": engine.losses,
                    "level": engine.level,
                    "max_win": engine.max_win_streak,
                    "max_loss": engine.max_loss_streak,
                    "mode": engine.state
                })
                last_pid = curr_pid
                
            time.sleep(2)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

t = threading.Thread(target=background_worker, daemon=True)
t.start()

# ==========================================
# 🌐 UI
# ==========================================
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TITAN V4 HYBRID</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;800&display=swap" rel="stylesheet">
<style>
    :root { --bg: #050505; --card: #111; --text: #fff; --accent: #6366f1; --win: #00ff88; --loss: #ff0055; }
    body { background: var(--bg); color: var(--text); font-family: 'JetBrains Mono', monospace; text-align: center; padding: 20px; }
    .container { max-width: 600px; margin: 0 auto; }
    
    .card { background: var(--card); border: 1px solid #222; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 30px rgba(0,0,0,0.5); }
    
    .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #333; padding-bottom: 15px; margin-bottom: 15px; }
    .title { font-weight: 800; font-size: 20px; color: var(--accent); }
    
    .stats-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }
    .stat-box { background: #1a1a1a; padding: 10px; border-radius: 8px; }
    .stat-label { font-size: 10px; color: #666; display: block; }
    .stat-val { font-size: 18px; font-weight: bold; }
    
    .pred-box { margin: 20px 0; }
    .big { color: var(--win); font-size: 60px; font-weight: 900; text-shadow: 0 0 20px rgba(0,255,136,0.2); }
    .small { color: var(--loss); font-size: 60px; font-weight: 900; text-shadow: 0 0 20px rgba(255,0,85,0.2); }
    .wait { color: #444; font-size: 40px; }
    
    .level-badge { background: #333; padding: 5px 10px; border-radius: 4px; font-size: 12px; color: #aaa; margin-top: 10px; display: inline-block; }
    
    .history-list { text-align: left; }
    .hist-item { display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid #222; font-size: 13px; }
    .hist-win { border-left: 3px solid var(--win); background: rgba(0,255,136,0.05); }
    .hist-loss { border-left: 3px solid var(--loss); background: rgba(255,0,85,0.05); }
    .hist-ghost { border-left: 3px solid #444; color: #666; }
</style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <div class="title">TITAN V4 HYBRID</div>
                <div style="font-size:12px; color:#666;">PERIOD: <span id="p">...</span></div>
            </div>
            
            <div class="stats-row">
                <div class="stat-box">
                    <span class="stat-label">NET SCORE</span>
                    <span style="color:var(--win)">W:<span id="w">0</span></span> / <span style="color:var(--loss)">L:<span id="l">0</span></span>
                </div>
                <div class="stat-box">
                    <span class="stat-label">CURRENT LEVEL</span>
                    <span class="stat-val" style="color:var(--accent)" id="lvl">1</span>
                </div>
            </div>
            <div class="stats-row">
                <div class="stat-box">
                    <span class="stat-label">MAX WIN STREAK</span>
                    <span class="stat-val" style="color:var(--win)" id="mw">0</span>
                </div>
                <div class="stat-box">
                    <span class="stat-label">MAX LOSS STREAK</span>
                    <span class="stat-val" style="color:var(--loss)" id="ml">0</span>
                </div>
            </div>

            <div class="pred-box">
                <div id="pred" class="wait">--</div>
                <div id="algo" class="level-badge">INITIALIZING...</div>
            </div>
        </div>

        <div id="hist" class="history-list"></div>
    </div>

<script>
    setInterval(() => {
        fetch('/api/status').then(r=>r.json()).then(d => {
            document.getElementById('p').innerText = d.period;
            document.getElementById('w').innerText = d.wins;
            document.getElementById('l').innerText = d.losses;
            document.getElementById('lvl').innerText = d.level;
            document.getElementById('mw').innerText = d.max_win;
            document.getElementById('ml').innerText = d.max_loss;
            
            let pEl = document.getElementById('pred');
            let aEl = document.getElementById('algo');
            
            pEl.innerText = d.prediction;
            pEl.className = d.prediction === "BIG" ? "big" : d.prediction === "SMALL" ? "small" : "wait";
            
            aEl.innerText = d.type;
            if(d.type.includes("CHAOS")) aEl.style.color = "#ffaa00";
            else if(d.type.includes("GHOST")) aEl.style.color = "#888";
            else aEl.style.color = "#aaa";
            
            document.getElementById('hist').innerHTML = d.history.map(h => {
                let cls = "hist-ghost";
                if(h.m === "REAL") cls = h.s.includes("WIN") ? "hist-win" : "hist-loss";
                return `<div class="hist-item ${cls}">
                    <span>#${h.p} <strong>${h.r}</strong></span>
                    <span>${h.s}</span>
                </div>`;
            }).join('');
        });
    }, 1500);
</script>
</body>
</html>
"""

@app.route('/')
def home(): return render_template_string(HTML)
@app.route('/api/status')
def status(): return jsonify(global_state)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5003)))
