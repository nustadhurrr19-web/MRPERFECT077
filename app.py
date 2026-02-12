import requests
import time
import threading
import os
import json
from collections import Counter, defaultdict
from flask import Flask, render_template_string, jsonify

# ==========================================
# ⚙️ CONFIGURATION & ML SETUP
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"
HISTORY_LIMIT = 500

# Try to import AI Libraries (Graceful Fallback)
ML_ACTIVE = False
try:
    from sklearn.ensemble import RandomForestClassifier
    import numpy as np
    ML_ACTIVE = True
    print("✅ ML LIBRARIES DETECTED: AI ENGINE ACTIVE")
except ImportError:
    print("⚠️ ML LIBRARIES MISSING: Running in MATH+PATTERN Mode")

app = Flask(__name__)

# ==========================================
# 🧠 TITAN V13: TRINITY BRAIN
# ==========================================
class TitanBrain:
    def __init__(self):
        self.history = []
        self.wins = 0
        self.losses = 0
        self.last_pred = None
        self.last_conf = "LOW"
        
        # --- ENGINES ---
        self.markov = defaultdict(lambda: {'BIG': 0, 'SMALL': 0})
        self.patterns = {
            "11111": 1, "00000": 0, "10101": 0, "01010": 1,
            "11001": 0, "00110": 1, "11100": 0, "00011": 1,
            "10010": 1, "01101": 0, "11011": 0, "00100": 1,
            "11101": 0, "00010": 1, "10001": 0, "01110": 1,
            "12121": 0, "11211": 1, "11110": 0, "00001": 1,
            "10000": 1, "01111": 0, "10111": 0, "01000": 1
        }
        
        # ML Model
        self.model = None
        if ML_ACTIVE:
            self.model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)

    def get_size(self, n): return 1 if int(n) >= 5 else 0
    def get_size_str(self, s): return "BIG" if s == 1 else "SMALL"

    def sync_data(self):
        """TURBO SYNC (2000 Records)"""
        try:
            print(f"🚀 SYNCING {HISTORY_LIMIT} RECORDS...")
            all_data = []
            
            # 1. Try Bulk
            try:
                r = requests.get(API_URL, params={"size": str(HISTORY_LIMIT), "pageNo": "1"}, timeout=5)
                if r.status_code == 200:
                    d = r.json().get('data', {}).get('list', [])
                    if len(d) > 100: all_data = d
            except: pass

            # 2. Fallback Loop
            if not all_data:
                for p in range(1, 41): 
                    r = requests.get(API_URL, params={"size": "50", "pageNo": str(p)}, timeout=3)
                    if r.status_code == 200:
                        d = r.json().get('data', {}).get('list', [])
                        if not d: break
                        all_data.extend(d)
            
            if not all_data: return False

            all_data.sort(key=lambda x: int(x['issueNumber']))
            self.history = [{'n': int(i['number']), 's': self.get_size(i['number']), 'id': str(i['issueNumber'])} for i in all_data]
            
            # Limit memory
            if len(self.history) > HISTORY_LIMIT:
                self.history = self.history[-HISTORY_LIMIT:]

            # Retrain All Engines
            self.train_markov()
            self.train_ml()
            return True
        except Exception as e:
            print(f"Sync Error: {e}")
            return False

    def train_markov(self):
        self.markov.clear()
        for i in range(3, len(self.history)):
            p = (self.history[i-3]['s'], self.history[i-2]['s'], self.history[i-1]['s'])
            r = 'BIG' if self.history[i]['s'] == 1 else 'SMALL'
            self.markov[p][r] += 1

    def train_ml(self):
        if not ML_ACTIVE or len(self.history) < 100: return
        
        X = []
        y = []
        # Create features: Last 5 results
        for i in range(5, len(self.history)):
            features = [self.history[i-k]['s'] for k in range(1, 6)]
            X.append(features)
            y.append(self.history[i]['s'])
        
        self.model.fit(X, y)

    def analyze(self):
        # 1. PATTERN ENGINE
        pat_vote = None
        if len(self.history) >= 6:
            seq = "".join([str(x['s']) for x in self.history[-5:]])
            pat_vote = self.patterns.get(seq)

        # 2. MATH ENGINE (Markov)
        math_vote = None
        math_conf = 0.5
        if len(self.history) >= 10:
            last3 = (self.history[-3]['s'], self.history[-2]['s'], self.history[-1]['s'])
            if last3 in self.markov:
                s = self.markov[last3]
                tot = s['BIG'] + s['SMALL']
                if tot > 0:
                    if s['BIG'] > s['SMALL']: 
                        math_vote = 1
                        math_conf = s['BIG']/tot
                    elif s['SMALL'] > s['BIG']: 
                        math_vote = 0
                        math_conf = s['SMALL']/tot

        # 3. AI ENGINE (ML)
        ml_vote = None
        ml_conf = 0.0
        if ML_ACTIVE and self.model and len(self.history) >= 6:
            features = [self.history[-k]['s'] for k in range(1, 6)]
            probs = self.model.predict_proba([features])[0]
            if probs[1] > probs[0]: 
                ml_vote = 1
                ml_conf = probs[1]
            else: 
                ml_vote = 0
                ml_conf = probs[0]

        # === FUSION LOGIC ===
        final_pred = None
        level = "LOW"
        sources = []

        # Tally Votes
        votes = {'BIG': 0, 'SMALL': 0}
        
        if pat_vote is not None: 
            k = 'BIG' if pat_vote==1 else 'SMALL'
            votes[k] += 1
            sources.append("PAT")
            
        if math_vote is not None and math_conf > 0.55:
            k = 'BIG' if math_vote==1 else 'SMALL'
            votes[k] += 1
            sources.append(f"MATH")
            
        if ml_vote is not None and ml_conf > 0.55:
            k = 'BIG' if ml_vote==1 else 'SMALL'
            votes[k] += 1.5 # AI vote counts more
            sources.append(f"AI")

        # Decision
        if votes['BIG'] > votes['SMALL']:
            final_pred = 1
            score = votes['BIG']
        elif votes['SMALL'] > votes['BIG']:
            final_pred = 0
            score = votes['SMALL']
        else:
            final_pred = self.history[-1]['s'] # Trend Follow Fallback
            score = 0
            sources = ["TREND"]

        # Confidence Grading
        if "AI" in sources and "PAT" in sources and "MATH" in sources:
            level = "SURESHOT"
        elif score >= 2:
            level = "HIGH"
        elif score >= 1:
            level = "GOOD"
        else:
            level = "LOW"

        # Format Source String
        src_str = " + ".join(sources[:2])
        if len(sources) > 2: src_str += "..."
        
        return final_pred, src_str, level

# ==========================================
# 🔄 WORKER
# ==========================================
bot = TitanBrain()
state = {
    "period": "...", "pred": "--", "source": "...", "level": "LOW",
    "wins": 0, "losses": 0, "data_count": 0, "history": []
}

def worker():
    last_id = None
    while True:
        try:
            if not bot.history: bot.sync_data()
            
            r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=4)
            d = r.json()['data']['list'][0]
            cid = str(d['issueNumber'])
            res = bot.get_size(d['number'])
            
            if cid != last_id:
                # 1. PROCESS
                status = "WAIT"
                if bot.last_pred is not None:
                    win = (bot.last_pred == res)
                    if win:
                        bot.wins += 1
                        status = "WIN"
                    else:
                        bot.losses += 1
                        status = "LOSS"
                    
                    state["history"].insert(0, {
                        "p": cid[-4:], 
                        "r": bot.get_size_str(res), 
                        "s": status, 
                        "l": bot.last_conf
                    })
                    state["history"] = state["history"][:25]

                # Update Data
                bot.history.append({'n': int(d['number']), 's': res, 'id': cid})
                bot.train_markov()
                bot.train_ml() # Re-train AI on new data
                if len(bot.history) > HISTORY_LIMIT: bot.history.pop(0)

                # 2. PREDICT
                pred, src, level = bot.analyze()
                bot.last_pred = pred
                bot.last_conf = level
                
                # Update UI
                pred_str = bot.get_size_str(pred) if pred is not None else "--"
                
                state.update({
                    "period": str(int(cid) + 1),
                    "pred": pred_str,
                    "source": src,
                    "level": level,
                    "wins": bot.wins,
                    "losses": bot.losses,
                    "data_count": len(bot.history)
                })
                last_id = cid
                
            time.sleep(1)
        except Exception as e:
            print(f"Loop Error: {e}")
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
<title>TITAN V13</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;700&display=swap" rel="stylesheet">
<style>
    :root { --bg:#050505; --card:#0f0f0f; --text:#e0e0e0; --accent:#00d4ff; --win:#00ff9d; --loss:#ff3d5e; }
    body { background: var(--bg); color: var(--text); font-family: 'Rajdhani', sans-serif; text-align: center; margin: 0; padding: 15px; }
    .container { max-width: 500px; margin: 0 auto; }
    
    /* DASHBOARD CARD */
    .dash { background: var(--card); border: 1px solid #222; border-radius: 12px; padding: 20px; box-shadow: 0 0 30px rgba(0, 212, 255, 0.1); margin-bottom: 20px; }
    
    .top-bar { display: flex; justify-content: space-between; font-size: 14px; color: #666; margin-bottom: 10px; }
    .data-meter { color: var(--accent); font-weight: bold; }
    
    .score { font-size: 28px; font-weight: bold; letter-spacing: 2px; margin-bottom: 5px; }
    .w { color: var(--win); } .l { color: var(--loss); }
    
    /* PREDICTION DISPLAY */
    .pred-area { margin: 25px 0; }
    .big { color: var(--win); font-size: 80px; font-weight: bold; text-shadow: 0 0 25px rgba(0, 255, 157, 0.2); line-height: 1; }
    .small { color: var(--loss); font-size: 80px; font-weight: bold; text-shadow: 0 0 25px rgba(255, 61, 94, 0.2); line-height: 1; }
    
    /* LOGIC BADGES */
    .logic-box { display: flex; justify-content: center; gap: 10px; align-items: center; margin-top: 15px; }
    .badge { padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: bold; text-transform: uppercase; }
    .b-src { background: #222; color: #888; border: 1px solid #333; }
    
    .lvl-badge { padding: 6px 14px; border-radius: 4px; font-size: 14px; font-weight: bold; color: #000; }
    .lvl-LOW { background: #555; color: #ccc; }
    .lvl-GOOD { background: #00d4ff; }
    .lvl-HIGH { background: #ff9100; }
    .lvl-SURESHOT { background: #d500f9; box-shadow: 0 0 15px #d500f9; animation: pulse 1s infinite; color: #fff; }
    
    /* HISTORY */
    .hist-header { text-align: left; font-size: 12px; color: #666; margin-bottom: 8px; padding-left: 5px; }
    .row { display: flex; justify-content: space-between; padding: 12px; background: #111; border-bottom: 1px solid #222; border-radius: 6px; margin-bottom: 4px; align-items: center; }
    .row.WIN { border-left: 4px solid var(--win); }
    .row.LOSS { border-left: 4px solid var(--loss); }
    .h-res { font-weight: bold; font-size: 16px; }
    .h-lvl { font-size: 10px; padding: 2px 6px; background: #222; border-radius: 3px; color: #888; margin-left: 8px; }

    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
    
    /* RESPONSIVE */
    @media (min-width: 600px) { .container { max-width: 600px; } .big, .small { font-size: 100px; } }
</style>
</head>
<body>
    <div class="container">
        <div class="dash">
            <div class="top-bar">
                <span>DATA: <span id="dm" class="data-meter">0</span>/2000</span>
                <span>PERIOD: <span id="p" style="color:#fff">...</span></span>
            </div>
            
            <div class="score">
                <span class="w">W:<span id="w">0</span></span>
                <span style="color:#333"> | </span>
                <span class="l">L:<span id="l">0</span></span>
            </div>
            
            <div class="pred-area">
                <div id="pred" class="big">--</div>
            </div>
            
            <div class="logic-box">
                <span id="src" class="badge b-src">AI + MATH</span>
                <span id="lvl" class="lvl-badge lvl-LOW">WAITING</span>
            </div>
        </div>
        
        <div class="hist-header">RECENT SIGNAL HISTORY</div>
        <div id="hist"></div>
    </div>

<script>
    setInterval(() => {
        fetch('/api/status').then(r=>r.json()).then(d => {
            document.getElementById('p').innerText = d.period;
            document.getElementById('w').innerText = d.wins;
            document.getElementById('l').innerText = d.losses;
            document.getElementById('dm').innerText = d.data_count;
            
            let pEl = document.getElementById('pred');
            pEl.innerText = d.pred;
            pEl.className = d.pred === "BIG" ? "big" : "small";
            
            document.getElementById('src').innerText = d.source;
            let lEl = document.getElementById('lvl');
            lEl.innerText = d.level;
            lEl.className = `lvl-badge lvl-${d.level}`;
            
            document.getElementById('hist').innerHTML = d.history.map(h => {
                let cls = h.s.includes("WIN") ? "WIN" : "LOSS";
                return `<div class="row ${cls}">
                    <div><span style="color:#444; margin-right:8px">#${h.p}</span> <span class="h-res">${h.r}</span></div>
                    <div><span style="font-weight:bold; color:${cls=='WIN'?'#00ff9d':'#ff3d5e'}">${h.s}</span> <span class="h-lvl">${h.l}</span></div>
                </div>`;
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
    app.run(host='0.0.0.0', port=5008)
