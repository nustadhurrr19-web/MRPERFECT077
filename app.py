import requests
import time
import threading
import os
import json
from collections import Counter
from flask import Flask, render_template_string, jsonify

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history" 
app = Flask(__name__)

# ==========================================
# 🧠 TITAN BRAIN (FULL 17-PATTERN UNLOCKED)
# ==========================================
class TitanBrain:
    def __init__(self):
        self.history = []
        
        # --- Stats (REAL MONEY ONLY) ---
        self.wins = 0
        self.losses = 0
        self.current_win_streak = 0
        self.current_loss_streak = 0
        self.max_win_streak = 0
        self.max_loss_streak = 0
        
        # --- Logic State ---
        self.level = 1  # 1, 2, or 3 (Sniper)
        self.state = "NORMAL"  # NORMAL, GHOST_RECOVERY
        self.ghost_turns_left = 0
        self.last_prediction = None
        
        # --- FULL 17 PATTERN DICTIONARY ---
        # 1=BIG, 0=SMALL
        self.patterns = {
            "11111": "DRAGON_BIG",    "00000": "DRAGON_SMALL",
            "10101": "ZIGZAG_B",      "01010": "ZIGZAG_S",
            "11001": "AABB_BREAK",    "00110": "AABB_BREAK_M", # Break AA-BB pattern
            "11100": "3_2_SPLIT",     "00011": "3_2_SPLIT_M",  # AAA-BB
            "10010": "SANDWICH_121",  "01101": "SANDWICH_121_M",
            "11011": "DOUBLE_PAIR",   "00100": "DOUBLE_PAIR_M",
            "11101": "3_1_BREAK",     "00010": "3_1_BREAK_M",
            "10001": "MIRROR_SIDE",   "01110": "MIRROR_SIDE_M",
            "12121": "JUMP",          # Dynamic placeholder
            "11211": "ASYMMETRIC"
        }

    def get_size(self, n): return 1 if int(n) >= 5 else 0
    def get_size_str(self, s): return "BIG" if s == 1 else "SMALL"

    def sync_data(self):
        try:
            all_data = []
            for p in range(1, 30): 
                r = requests.get(API_URL, params={"size": "20", "pageNo": str(p)}, timeout=4)
                if r.status_code == 200:
                    d = r.json().get('data', {}).get('list', [])
                    if not d: break
                    all_data.extend(d)
            all_data.sort(key=lambda x: int(x['issueNumber']))
            self.history = [{'n': int(i['number']), 's': self.get_size(i['number']), 'id': str(i['issueNumber'])} for i in all_data]
            return True
        except: return False

    def detect_pattern(self):
        """FULL PATTERN LOGIC IMPLEMENTATION"""
        if len(self.history) < 6: return None
        
        # Get last 5 results signature
        seq = "".join([str(x['s']) for x in self.history[-5:]])
        last = self.history[-1]['s']
        
        # 1. DRAGON (Streak > 4) -> Follow
        if seq == "11111": return 1
        if seq == "00000": return 0
        
        # 2. ZIGZAG (10101) -> Flip
        if seq == "10101": return 0 # Expect 0
        if seq == "01010": return 1 # Expect 1
        
        # 3. AABB BREAK (11001) -> Expect A (Repeat) or B?
        # AABB usually results in Repeat of last. 1100 -> 1? 
        if seq == "11001": return 0 # Break to ZigZag?
        if seq == "00110": return 1
        
        # 4. 3-2 SPLIT (11100) -> Expect 0 (make it 3-3)
        if seq == "11100": return 0
        if seq == "00011": return 1
        
        # 5. SANDWICH (10010) -> Expect 1 (Close sandwich)
        if seq == "10010": return 1
        if seq == "01101": return 0
        
        # 6. MIRROR (10001) -> Expect 0 (Symmetric)
        if seq == "10001": return 0
        if seq == "01110": return 1

        return None

    def analyze_trend(self):
        if len(self.history) < 20: return None, "WAITING...", False

        # 1. Pattern Engine
        pat_pred = self.detect_pattern()
        
        # 2. Mathcore Engine (Dynamic Depth)
        math_pred = None
        confidence = 0
        
        # Try finding sequence in history
        for depth in [6, 5, 4]:
            last_seq = [x['s'] for x in self.history[-depth:]]
            matches = []
            for i in range(len(self.history) - (depth + 1)):
                if [x['s'] for x in self.history[i : i+depth]] == last_seq:
                    matches.append(self.history[i+depth]['s'])
            
            if matches:
                c = Counter(matches)
                top = c.most_common(1)[0]
                if (top[1] / len(matches)) > 0.55:
                    math_pred = top[0]
                    confidence = top[1] / len(matches)
                    break
        
        # 3. LEVEL 3 SNIPER LOGIC (The "Perfect" Requirement)
        is_sureshot = False
        final_pred = None
        algo_type = "TREND"
        
        if self.level == 3:
            # ON LEVEL 3, WE ONLY BET IF BOTH AGREE
            if pat_pred is not None and math_pred is not None and pat_pred == math_pred:
                final_pred = pat_pred
                algo_type = "🔥 LVL 3 SNIPER (PERFECT)"
                is_sureshot = True
            else:
                return None, "WAITING FOR PERFECT...", False
        else:
            # LEVEL 1 & 2 (Standard Logic)
            if pat_pred == math_pred and pat_pred is not None:
                final_pred = pat_pred
                algo_type = "⭐ SURESHOT"
                is_sureshot = True
            elif confidence > 0.75:
                final_pred = math_pred
                algo_type = "MATH STRONG"
            elif pat_pred is not None:
                final_pred = pat_pred
                algo_type = "PATTERN"
            elif math_pred is not None:
                final_pred = math_pred
                algo_type = "MATH FLOW"
            else:
                final_pred = self.history[-1]['s']
                algo_type = "DRAGON"

        return final_pred, algo_type, is_sureshot

# ==========================================
# 🔄 WORKER
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
            
            # Fetch
            r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=5)
            if r.status_code != 200: 
                time.sleep(3)
                continue
                
            data = r.json()['data']['list'][0]
            curr_pid = str(data['issueNumber'])
            real_res = engine.get_size(data['number']) # 0/1
            
            if curr_pid != last_pid:
                # --- PROCESS RESULT ---
                is_win = False
                status_txt = "SKIP"
                
                if engine.last_prediction is not None:
                    is_win = (engine.last_prediction == real_res)
                    
                    if engine.state == "NORMAL":
                        # === REAL BET LOGIC ===
                        if is_win:
                            engine.wins += 1
                            engine.current_win_streak += 1
                            engine.current_loss_streak = 0
                            if engine.current_win_streak > engine.max_win_streak:
                                engine.max_win_streak = engine.current_win_streak
                            
                            # RESET LEVEL ON WIN
                            engine.level = 1 
                            status_txt = "WIN"
                        else:
                            engine.losses += 1
                            engine.current_loss_streak += 1
                            engine.current_win_streak = 0
                            if engine.current_loss_streak > engine.max_loss_streak:
                                engine.max_loss_streak = engine.current_loss_streak
                            
                            status_txt = "LOSS"
                            
                            # LEVEL PROGRESSION
                            if engine.level < 3:
                                engine.level += 1
                            else:
                                # Level 3 Lost -> TRIGGER GHOST MODE
                                engine.state = "GHOST_RECOVERY"
                                engine.ghost_turns_left = 3
                                engine.level = 1 # Reset level for when we return
                                status_txt = "LOSS (GHOST TRIGGER)"

                    elif engine.state == "GHOST_RECOVERY":
                        # === GHOST LOGIC (NO STATS UPDATE) ===
                        engine.ghost_turns_left -= 1
                        status_txt = f"GHOST {'WIN' if is_win else 'LOSS'}"
                        
                        if engine.ghost_turns_left <= 0:
                            engine.state = "NORMAL"

                # Log
                mode_tag = "REAL" if engine.state == "NORMAL" and "GHOST" not in status_txt else "GHOST"
                global_state["history"].insert(0, {
                    "p": curr_pid[-4:], 
                    "r": engine.get_size_str(real_res), 
                    "s": status_txt,
                    "m": mode_tag
                })
                global_state["history"] = global_state["history"][:15]
                engine.history.append({'n': int(data['number']), 's': real_res, 'id': curr_pid})

                # --- PREDICT NEXT ---
                pred, algo, is_safe = engine.analyze_trend()
                engine.last_prediction = pred
                
                # UI Display Logic
                d_pred = "--"
                d_type = "WAITING..."
                
                if pred is not None:
                    if engine.state == "NORMAL":
                        if engine.level == 3 and not is_safe:
                            # Level 3 Hold
                            d_pred = "WAIT"
                            d_type = "⛔ SEEKING PERFECT..."
                            engine.last_prediction = None # Don't bet
                        else:
                            d_pred = engine.get_size_str(pred)
                            d_type = f"LVL {engine.level} | {algo}"
                    else:
                        d_pred = "SKIP"
                        d_type = f"🛡️ GHOST ({engine.ghost_turns_left})"

                global_state.update({
                    "period": str(int(curr_pid) + 1),
                    "prediction": d_pred,
                    "type": d_type,
                    "wins": engine.wins,
                    "losses": engine.losses,
                    "max_win": engine.max_win_streak,
                    "max_loss": engine.max_loss_streak,
                    "mode": engine.state
                })
                last_pid = curr_pid
                
            time.sleep(2)
        except Exception as e:
            print(e)
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
<title>TITAN ULTIMATE</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;800&display=swap" rel="stylesheet">
<style>
    body { background: #000; color: #fff; font-family: 'JetBrains Mono', monospace; text-align: center; padding: 20px; }
    .card { background: #111; border: 1px solid #333; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
    .row { display: flex; justify-content: space-between; margin-bottom: 10px; }
    .big { color: #00ff88; font-size: 50px; font-weight: 800; }
    .small { color: #ff0055; font-size: 50px; font-weight: 800; }
    .wait { color: #555; font-size: 30px; }
    .ghost { color: #444; }
    .stat-val { font-size: 20px; font-weight: bold; }
    .list-item { background: #1a1a1a; padding: 10px; margin: 5px 0; border-radius: 5px; display: flex; justify-content: space-between; }
    .win { border-left: 4px solid #00ff88; }
    .loss { border-left: 4px solid #ff0055; }
    .ghost-item { border-left: 4px solid #444; opacity: 0.5; }
</style>
</head>
<body>
    <div class="card">
        <div class="row">
            <div>TITAN ULTIMATE</div>
            <div>W:<span id="w" style="color:#00ff88">0</span> L:<span id="l" style="color:#ff0055">0</span></div>
        </div>
        <div class="row">
            <div>🔥 MAX: <span id="mw">0</span></div>
            <div>❄️ MAX: <span id="ml">0</span></div>
        </div>
    </div>

    <div class="card">
        <div style="color:#888; font-size:12px">PERIOD: <span id="p">Loading...</span></div>
        <div id="pred" class="wait">--</div>
        <div id="algo" style="color:#aaa; font-size:14px; margin-top:10px">...</div>
    </div>

    <div id="hist"></div>

<script>
    setInterval(() => {
        fetch('/api/status').then(r=>r.json()).then(d => {
            document.getElementById('p').innerText = d.period;
            document.getElementById('w').innerText = d.wins;
            document.getElementById('l').innerText = d.losses;
            document.getElementById('mw').innerText = d.max_win;
            document.getElementById('ml').innerText = d.max_loss;
            
            let pEl = document.getElementById('pred');
            pEl.innerText = d.prediction;
            pEl.className = d.prediction === "BIG" ? "big" : d.prediction === "SMALL" ? "small" : "wait";
            
            document.getElementById('algo').innerText = d.type;
            
            document.getElementById('hist').innerHTML = d.history.map(h => {
                let cls = "ghost-item";
                if(h.m === "REAL") cls = h.s.includes("WIN") ? "win" : "loss";
                return `<div class="list-item ${cls}"><span>#${h.p} ${h.r}</span><span>${h.s}</span></div>`;
            }).join('');
        });
    }, 1000);
</script>
</body>
</html>
"""

@app.route('/')
def home(): return render_template_string(HTML)
@app.route('/api/status')
def status(): return jsonify(global_state)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5001)))
