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
# 🧠 TITAN PURE: LOGIC CORE
# ==========================================
class TitanBrain:
    def __init__(self):
        self.history = []
        
        # --- Stats ---
        self.wins = 0
        self.losses = 0
        self.current_loss_streak = 0
        self.max_win_streak = 0
        self.max_loss_streak = 0
        
        # --- State ---
        self.state = "NORMAL" # NORMAL or GHOST
        self.ghost_turns = 0
        self.last_prediction = None
        self.last_conf_level = "LOW" # LOW, HIGH, SURESHOT
        
        # --- MATH MEMORY ---
        self.markov = defaultdict(lambda: {'BIG': 0, 'SMALL': 0})

        # --- PATTERNS ---
        self.patterns = {
            "11111": 1, "00000": 0, "10101": 0, "01010": 1,
            "11001": 0, "00110": 1, "11100": 0, "00011": 1,
            "10010": 1, "01101": 0, "11011": 0, "00100": 1,
            "11101": 0, "00010": 1, "10001": 0, "01110": 1,
            "12121": 0, "11211": 1, "11110": 0, "00001": 1,
            "10000": 1, "01111": 0, "10111": 0, "01000": 1
        }

    def get_size(self, n): return 1 if int(n) >= 5 else 0
    def get_size_str(self, s): return "BIG" if s == 1 else "SMALL"

    def sync_data(self):
        """INSTANT 1000-ROUND SYNC"""
        try:
            print("🚀 SYNCING DATA...")
            all_data = []
            
            # Try Bulk Fetch
            try:
                r = requests.get(API_URL, params={"size": "1000", "pageNo": "1"}, timeout=5)
                if r.status_code == 200:
                    d = r.json().get('data', {}).get('list', [])
                    if len(d) > 100: all_data = d
            except: pass

            # Fallback Loop
            if not all_data:
                for p in range(1, 21): 
                    r = requests.get(API_URL, params={"size": "50", "pageNo": str(p)}, timeout=3)
                    if r.status_code == 200:
                        d = r.json().get('data', {}).get('list', [])
                        if not d: break
                        all_data.extend(d)
            
            if not all_data: return False

            # Sort & Store
            all_data.sort(key=lambda x: int(x['issueNumber']))
            self.history = [{'n': int(i['number']), 's': self.get_size(i['number']), 'id': str(i['issueNumber'])} for i in all_data]
            
            # Train Math
            self.train_markov()
            return True
        except: return False

    def train_markov(self):
        self.markov.clear()
        for i in range(3, len(self.history)):
            p = (self.history[i-3]['s'], self.history[i-2]['s'], self.history[i-1]['s'])
            r = 'BIG' if self.history[i]['s'] == 1 else 'SMALL'
            self.markov[p][r] += 1

    def get_prediction(self):
        if self.state == "GHOST":
            return None, f"🛡️ GHOST MODE ({self.ghost_turns})", "SKIP"

        # 1. GET INPUTS
        # Pattern Engine
        pat_res = None
        if len(self.history) >= 6:
            seq = "".join([str(x['s']) for x in self.history[-5:]])
            pat_res = self.patterns.get(seq)
            if pat_res is None: # Fallback checks
                if seq == "11111": pat_res = 1
                if seq == "00000": pat_res = 0

        # Math Engine
        math_res = None
        math_conf = 0.0
        if len(self.history) >= 10:
            last3 = (self.history[-3]['s'], self.history[-2]['s'], self.history[-1]['s'])
            if last3 in self.markov:
                s = self.markov[last3]
                tot = s['BIG'] + s['SMALL']
                if tot > 0:
                    if s['BIG'] > s['SMALL']: 
                        math_res = 1
                        math_conf = s['BIG']/tot
                    elif s['SMALL'] > s['BIG']: 
                        math_res = 0
                        math_conf = s['SMALL']/tot

        # 2. CALCULATE CONFIDENCE LEVEL
        final_pred = None
        level = "LOW"
        desc = "WAITING"

        # TIER 3: SURESHOT (Agree + Strong Math)
        if pat_res is not None and math_res is not None and pat_res == math_res and math_conf > 0.80:
            final_pred = pat_res
            level = "SURESHOT"
            desc = f"🔥 SURESHOT ({int(math_conf*100)}%)"

        # TIER 2: HIGH BET (Agree OR Strong Math)
        elif pat_res is not None and math_res is not None and pat_res == math_res:
            final_pred = pat_res
            level = "HIGH"
            desc = f"🟡 HIGH BET (AGREEMENT)"
        elif math_res is not None and math_conf > 0.70:
            final_pred = math_res
            level = "HIGH"
            desc = f"🟡 HIGH BET (MATH {int(math_conf*100)}%)"

        # TIER 1: LOW BET (Any Signal)
        elif pat_res is not None:
            final_pred = pat_res
            level = "LOW"
            desc = "🟢 LOW BET (PATTERN)"
        elif math_res is not None:
            final_pred = math_res
            level = "LOW"
            desc = f"🟢 LOW BET (FLOW {int(math_conf*100)}%)"
        
        # Fallback (If literally nothing matches, follow trend)
        else:
             final_pred = self.history[-1]['s']
             level = "LOW"
             desc = "🟢 LOW BET (TREND)"

        return final_pred, desc, level

# ==========================================
# 🔄 WORKER
# ==========================================
bot = TitanBrain()
state = {
    "period": "...", "pred": "--", "type": "...", "level": "LOW",
    "wins": 0, "losses": 0, "streak": 0, "history": []
}

def worker():
    last_id = None
    while True:
        try:
            if not bot.history: bot.sync_data()
            
            # Fetch
            r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=4)
            d = r.json()['data']['list'][0]
            cid = str(d['issueNumber'])
            res = bot.get_size(d['number'])
            
            if cid != last_id:
                # 1. PROCESS LAST ROUND
                win = False
                status = "SKIP"
                
                # Update Data
                bot.history.append({'n': int(d['number']), 's': res, 'id': cid})
                bot.train_markov()
                if len(bot.history) > 2000: bot.history.pop(0)

                # Check Prediction
                if bot.last_prediction is not None:
                    win = (bot.last_prediction == res)
                    
                    if bot.state == "NORMAL":
                        if win:
                            bot.wins += 1
                            bot.current_loss_streak = 0
                            status = "WIN"
                        else:
                            bot.losses += 1
                            bot.current_loss_streak += 1
                            status = "LOSS"
                            # SAFETY: 2 Losses = Ghost Mode
                            if bot.current_loss_streak >= 2:
                                bot.state = "GHOST"
                                bot.ghost_turns = 3
                                status = "LOSS (GHOST TRIGGER)"
                    
                    else: # GHOST MODE
                        bot.ghost_turns -= 1
                        status = f"GHOST {'WIN' if win else 'LOSS'}"
                        if bot.ghost_turns <= 0:
                            bot.state = "NORMAL"
                            bot.current_loss_streak = 0

                # Log
                if bot.last_prediction is not None or "TRIGGER" in status:
                    state["history"].insert(0, {
                        "p": cid[-4:], "r": bot.get_size_str(res), 
                        "s": status, "l": bot.last_conf_level
                    })
                    state["history"] = state["history"][:20]

                # 2. PREDICT NEXT
                pred, desc, level = bot.get_prediction()
                bot.last_prediction = pred
                bot.last_conf_level = level
                
                # Update UI
                pred_str = "--"
                if pred is not None:
                    pred_str = bot.get_size_str(pred)
                elif bot.state == "GHOST":
                    pred_str = "SKIP"
                
                state.update({
                    "period": str(int(cid) + 1),
                    "pred": pred_str,
                    "type": desc,
                    "level": level,
                    "wins": bot.wins,
                    "losses": bot.losses
                })
                last_id = cid
                
            time.sleep(2)
        except Exception as e:
            print(e)
            time.sleep(5)

threading.Thread(target=worker, daemon=True).start()

# ==========================================
# 🌐 UI
# ==========================================
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TITAN PURE</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
<style>
    body { background: #000; color: #fff; font-family: 'Inter', sans-serif; text-align: center; padding: 20px; }
    .card { background: #111; border: 1px solid #222; padding: 20px; border-radius: 16px; margin-bottom: 20px; }
    
    .score { display: flex; justify-content: space-between; font-weight: bold; font-size: 18px; margin-bottom: 10px; }
    .w { color: #4ade80; } .l { color: #f87171; }
    
    .pred-box { padding: 30px 0; }
    .p-big { color: #4ade80; font-size: 72px; font-weight: 900; text-shadow: 0 0 30px rgba(74, 222, 128, 0.2); }
    .p-small { color: #f87171; font-size: 72px; font-weight: 900; text-shadow: 0 0 30px rgba(248, 113, 113, 0.2); }
    .p-skip { color: #555; font-size: 40px; font-weight: bold; }
    
    .badge { padding: 8px 16px; border-radius: 8px; font-size: 14px; font-weight: bold; display: inline-block; }
    .b-low { background: #1e3a8a; color: #93c5fd; }
    .b-high { background: #854d0e; color: #fef08a; }
    .b-sure { background: #831843; color: #fbcfe8; border: 1px solid #f472b6; box-shadow: 0 0 15px rgba(244, 114, 182, 0.3); }
    .b-ghost { background: #333; color: #888; }
    
    .row { display: flex; justify-content: space-between; padding: 12px; border-bottom: 1px solid #222; font-size: 14px; }
    .win { border-left: 3px solid #4ade80; background: #052e16; }
    .loss { border-left: 3px solid #f87171; background: #2e0505; }
    .ghost { border-left: 3px solid #444; color: #666; }
</style>
</head>
<body>
    <div class="card">
        <div class="score">
            <span>TITAN PURE</span>
            <span><span class="w" id="w">0</span> / <span class="l" id="l">0</span></span>
        </div>
        <div style="color:#666; font-size:12px">PERIOD: <span id="p">...</span></div>
        
        <div class="pred-box">
            <div id="pred" class="p-skip">--</div>
            <div style="margin-top:15px"><span id="type" class="badge b-ghost">INITIALIZING...</span></div>
        </div>
    </div>
    
    <div id="hist"></div>

<script>
    setInterval(() => {
        fetch('/api/status').then(r=>r.json()).then(d => {
            document.getElementById('p').innerText = d.period;
            document.getElementById('w').innerText = d.wins;
            document.getElementById('l').innerText = d.losses;
            
            let pEl = document.getElementById('pred');
            if(d.pred === "BIG") pEl.className = "p-big";
            else if(d.pred === "SMALL") pEl.className = "p-small";
            else pEl.className = "p-skip";
            pEl.innerText = d.pred;
            
            let tEl = document.getElementById('type');
            tEl.innerText = d.type;
            tEl.className = "badge " + (
                d.level === "SURESHOT" ? "b-sure" : 
                d.level === "HIGH" ? "b-high" : 
                d.pred === "SKIP" ? "b-ghost" : "b-low"
            );
            
            document.getElementById('hist').innerHTML = d.history.map(h => {
                let c = "ghost";
                if(h.s.includes("WIN") && !h.s.includes("GHOST")) c = "win";
                if(h.s.includes("LOSS") && !h.s.includes("GHOST")) c = "loss";
                return `<div class="row ${c}"><span>#${h.p} ${h.r}</span><span>${h.s}</span></div>`;
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
def status(): return jsonify(state)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5003)))
