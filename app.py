import requests
import time
import threading
import os
from collections import defaultdict
from flask import Flask, render_template_string, jsonify

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"
app = Flask(__name__)

# ==========================================
# 🧠 TITAN V11: AGGRESSIVE ANALYST
# ==========================================
class TitanBrain:
    def __init__(self):
        self.history = []
        self.wins = 0
        self.losses = 0
        self.last_pred = None
        
        # --- MATH MEMORY ---
        self.markov = defaultdict(lambda: {'BIG': 0, 'SMALL': 0})

        # --- PATTERNS (24 Rules) ---
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
        """INSTANT BULK SYNC"""
        try:
            print("🚀 FETCHING DATA...")
            all_data = []
            try:
                # Attempt 1000 records fetch
                r = requests.get(API_URL, params={"size": "1000", "pageNo": "1"}, timeout=5)
                if r.status_code == 200:
                    d = r.json().get('data', {}).get('list', [])
                    if len(d) > 100: all_data = d
            except: pass

            if not all_data:
                # Fallback Loop
                for p in range(1, 21): 
                    r = requests.get(API_URL, params={"size": "50", "pageNo": str(p)}, timeout=3)
                    if r.status_code == 200:
                        d = r.json().get('data', {}).get('list', [])
                        if not d: break
                        all_data.extend(d)
            
            if not all_data: return False

            all_data.sort(key=lambda x: int(x['issueNumber']))
            self.history = [{'n': int(i['number']), 's': self.get_size(i['number']), 'id': str(i['issueNumber'])} for i in all_data]
            self.train_markov()
            return True
        except: return False

    def train_markov(self):
        self.markov.clear()
        for i in range(3, len(self.history)):
            p = (self.history[i-3]['s'], self.history[i-2]['s'], self.history[i-1]['s'])
            r = 'BIG' if self.history[i]['s'] == 1 else 'SMALL'
            self.markov[p][r] += 1

    def analyze(self):
        # 1. GET SIGNALS
        # Pattern Engine
        pat_res = None
        if len(self.history) >= 6:
            seq = "".join([str(x['s']) for x in self.history[-5:]])
            pat_res = self.patterns.get(seq)
            if pat_res is None: 
                # Basic Trends
                if seq == "11111": pat_res = 1
                if seq == "00000": pat_res = 0

        # Math Engine (Markov)
        math_res = None
        math_conf = 0.50
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

        # 2. AGGRESSIVE DECISION LOGIC
        final_pred = None
        quality = "LOW"
        desc = "RANDOM"

        # PRIORITY 1: SURESHOT (Consensus + High Conf)
        if pat_res is not None and math_res is not None and pat_res == math_res and math_conf > 0.80:
            final_pred = pat_res
            quality = "SURESHOT"
            desc = f"🔥 SURESHOT ({int(math_conf*100)}%)"

        # PRIORITY 2: HIGH (Consensus)
        elif pat_res is not None and math_res is not None and pat_res == math_res:
            final_pred = pat_res
            quality = "HIGH"
            desc = f"✅ STRONG AGREE"

        # PRIORITY 3: GOOD (Strong Math)
        elif math_res is not None and math_conf > 0.65:
            final_pred = math_res
            quality = "GOOD"
            desc = f"📊 MATH {int(math_conf*100)}%"

        # PRIORITY 4: LOW (Pattern Only)
        elif pat_res is not None:
            final_pred = pat_res
            quality = "LOW"
            desc = "⚠️ PATTERN ONLY"

        # PRIORITY 5: LOW (Weak Math)
        elif math_res is not None and math_conf > 0.51:
            final_pred = math_res
            quality = "LOW"
            desc = f"⚠️ WEAK FLOW {int(math_conf*100)}%"
            
        # PRIORITY 6: FORCE PREDICTION (Trend Follow)
        else:
            final_pred = self.history[-1]['s']
            quality = "LOW"
            desc = "⚠️ TREND FOLLOW"

        return final_pred, desc, quality

# ==========================================
# 🔄 WORKER
# ==========================================
bot = TitanBrain()
state = {
    "period": "...", "pred": "--", "type": "...", "quality": "LOW",
    "wins": 0, "losses": 0, "history": []
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
                # 1. PROCESS RESULT
                win = False
                status = "Wait"
                
                # Update Data
                bot.history.append({'n': int(d['number']), 's': res, 'id': cid})
                bot.train_markov()
                if len(bot.history) > 2000: bot.history.pop(0)

                # Check Previous Prediction
                if bot.last_pred is not None:
                    win = (bot.last_pred == res)
                    if win:
                        bot.wins += 1
                        status = "WIN"
                    else:
                        bot.losses += 1
                        status = "LOSS"
                    
                    # Add to History
                    state["history"].insert(0, {
                        "p": cid[-4:], "r": bot.get_size_str(res), 
                        "s": status, "q": "REAL"
                    })
                    state["history"] = state["history"][:20]

                # 2. PREDICT NEXT (AGGRESSIVE)
                pred, desc, quality = bot.analyze()
                bot.last_pred = pred
                
                # Update UI
                state.update({
                    "period": str(int(cid) + 1),
                    "pred": bot.get_size_str(pred),
                    "type": desc,
                    "quality": quality,
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
<title>TITAN V11 AGGRESSIVE</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap" rel="stylesheet">
<style>
    body { background: #000; color: #fff; font-family: 'Inter', sans-serif; text-align: center; padding: 20px; }
    .card { background: #111; border: 1px solid #222; padding: 20px; border-radius: 16px; margin-bottom: 20px; }
    
    .score { display: flex; justify-content: center; font-weight: bold; font-size: 20px; margin-bottom: 10px; gap: 20px; }
    .w { color: #4ade80; } .l { color: #f87171; }
    
    .pred-box { padding: 30px 0; }
    .p-big { color: #4ade80; font-size: 80px; font-weight: 900; text-shadow: 0 0 40px rgba(74, 222, 128, 0.2); }
    .p-small { color: #f87171; font-size: 80px; font-weight: 900; text-shadow: 0 0 40px rgba(248, 113, 113, 0.2); }
    
    .badge { padding: 10px 20px; border-radius: 8px; font-size: 16px; font-weight: bold; display: inline-block; text-transform: uppercase; }
    .b-low { background: #333; color: #888; border: 1px solid #444; }
    .b-good { background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; }
    .b-high { background: #854d0e; color: #fef08a; border: 1px solid #eab308; }
    .b-sure { background: #831843; color: #fbcfe8; border: 1px solid #f472b6; box-shadow: 0 0 20px rgba(244, 114, 182, 0.4); animation: pulse 1.5s infinite; }
    
    .row { display: flex; justify-content: space-between; padding: 12px; border-bottom: 1px solid #222; font-size: 14px; align-items: center; }
    .win { border-left: 4px solid #4ade80; background: #052e16; }
    .loss { border-left: 4px solid #f87171; background: #2e0505; }
    
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.8; } 100% { opacity: 1; } }
</style>
</head>
<body>
    <div class="card">
        <div class="score">
            <span>W: <span class="w" id="w">0</span></span>
            <span>L: <span class="l" id="l">0</span></span>
        </div>
        <div style="color:#666; font-size:12px; margin-bottom:10px">PERIOD: <span id="p">...</span></div>
        
        <div class="pred-box">
            <div id="pred" class="p-big">--</div>
            <div style="margin-top:20px"><span id="qual" class="badge b-low">LOADING...</span></div>
            <div id="desc" style="color:#666; font-size:12px; margin-top:10px;">...</div>
        </div>
    </div>
    
    <div id="hist"></div>

<script>
    setInterval(() => {
        fetch('/api/status').then(r=>r.json()).then(d => {
            document.getElementById('p').innerText = d.period;
            document.getElementById('w').innerText = d.wins;
            document.getElementById('l').innerText = d.losses;
            document.getElementById('desc').innerText = d.type;
            
            let pEl = document.getElementById('pred');
            pEl.className = d.pred === "BIG" ? "p-big" : "p-small";
            pEl.innerText = d.pred;
            
            let qEl = document.getElementById('qual');
            qEl.innerText = d.quality;
            qEl.className = "badge " + (
                d.quality === "SURESHOT" ? "b-sure" : 
                d.quality === "HIGH" ? "b-high" : 
                d.quality === "GOOD" ? "b-good" : "b-low"
            );
            
            document.getElementById('hist').innerHTML = d.history.map(h => {
                let c = h.s === "WIN" ? "win" : "loss";
                return `<div class="row ${c}">
                    <span>#${h.p} ${h.r}</span>
                    <span>${h.s}</span>
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
    port = int(os.environ.get("PORT", 5003))
    app.run(host='0.0.0.0', port=port)
