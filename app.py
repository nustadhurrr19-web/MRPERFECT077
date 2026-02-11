import requests
import time
import threading
import datetime
import os
import sys
from collections import Counter
from flask import Flask, render_template_string

# ==========================================
# ⚙️ TITAN V8 CONFIGURATION (ULTIMATE ACTION)
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"

# LOGIC SETTINGS
BASE_THRESHOLD = 0.55       # Level 1-2: Bet on anything > 55%
RECOVERY_THRESHOLD = 0.70   # Level 3: Needs 70% Confidence
SNIPER_THRESHOLD = 0.85     # Level 4: Needs 85% Confidence (Safety Net)
MIN_MATCHES = 2             # Only need 2 past matches to vote (Very Aggressive)

# ==========================================
# 📊 SHARED STATE
# ==========================================
class GameState:
    def __init__(self):
        self.history = []
        self.active_bet = None 
        self.last_result = None 
        self.stats = {'wins': 0, 'losses': 0, 'skips': 0}
        self.logs = []          
        self.current_round = "WAITING"
        self.streak_loss = 0    
        self.cooldown = 0       

state = GameState()

# ==========================================
# 🧠 TITAN BRAIN V8
# ==========================================
class TitanBrain:
    def get_size(self, n): 
        return "BIG" if int(n) >= 5 else "SMALL"

    def log(self, msg):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}", flush=True) 
        state.logs.insert(0, f"[{timestamp}] {msg}")
        if len(state.logs) > 50: state.logs.pop()

    def sync_data(self):
        try:
            all_data = []
            # WAKE UP CALL (60s Timeout)
            self.log("📡 Syncing Data...")
            r = requests.get(API_URL, params={"size": "20", "pageNo": "1"}, timeout=60)
            
            if r.status_code == 200:
                data = r.json().get('data', {}).get('list', [])
                all_data.extend(data)
            else:
                self.log(f"⚠️ API Status: {r.status_code}")
                return False

            # FAST FETCH (Pages 2-5)
            for p in range(2, 6): 
                try:
                    r = requests.get(API_URL, params={"size": "20", "pageNo": str(p)}, timeout=10)
                    if r.status_code == 200:
                        data = r.json().get('data', {}).get('list', [])
                        all_data.extend(data)
                except: pass

            if not all_data: return False

            all_data.sort(key=lambda x: int(x['issueNumber']))
            state.history = [{
                'n': int(item['number']), 
                's': self.get_size(item['number']), 
                'id': str(item['issueNumber'])
            } for item in all_data]
            
            return True
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            return False

    # --- 1. PATTERN ENGINE (Hyper Sensitive) ---
    def get_pattern_signal(self, depth):
        if len(state.history) < depth + 1: return None, 0, "NONE"
        
        current_seq = [x['s'] for x in state.history[-depth:]]
        matches = []
        
        for i in range(len(state.history) - (depth + 1)):
            window = [x['s'] for x in state.history[i : i+depth]]
            if window == current_seq:
                outcome = state.history[i+depth]['s']
                matches.append(outcome)
        
        # V8 UPDATE: Min Matches lowered to 2
        if len(matches) < MIN_MATCHES: 
            return None, 0, "NO_DATA"

        counts = Counter(matches)
        top = counts.most_common(1)[0]
        conf = top[1] / len(matches)
        
        # Reverse Logic included
        if conf < 0.20:
             rev = "SMALL" if top[0] == "BIG" else "BIG"
             return rev, (1.0 - conf), "REVERSE"
             
        return top[0], conf, "PATTERN"

    # --- 2. NUMBER BIAS (Hyper Sensitive) ---
    def get_number_bias(self, target_num):
        matches = [x for x in state.history[:-1] if x['n'] == target_num]
        if len(matches) < 2: return None, 0.0 # V8 UPDATE: Min 2 matches

        next_indices = [state.history.index(m) + 1 for m in matches if state.history.index(m) + 1 < len(state.history)]
        outcomes = [state.history[i]['s'] for i in next_indices]
        if not outcomes: return None, 0.0
        
        top = Counter(outcomes).most_common(1)[0]
        return top[0], top[1] / len(outcomes)

    # --- MASTER ANALYZE V8 ---
    def analyze(self):
        # [A] COOLDOWN CHECK
        if state.cooldown > 0:
            state.cooldown -= 1
            return None 

        # [B] GATHER ALL SIGNALS
        p5, c5, t5 = self.get_pattern_signal(5) 
        p4, c4, t4 = self.get_pattern_signal(4) 
        last_digit = state.history[-1]['n']
        n_pred, n_conf = self.get_number_bias(last_digit)

        # [C] VOTE WEIGHTING
        votes_big = 0
        votes_small = 0
        score_max = 0
        
        # Force Engines to contribute if they have ANY data
        if p5: 
            w=2.0; score_max+=w
            if p5=="BIG": votes_big+=c5*w 
            else: votes_small+=c5*w
        if p4:
            w=1.5; score_max+=w
            if p4=="BIG": votes_big+=c4*w 
            else: votes_small+=c4*w
        if n_pred:
            w=1.0; score_max+=w
            if n_pred=="BIG": votes_big+=n_conf*w 
            else: votes_small+=n_conf*w

        # [D] FORCE ACTION (Zero Data Fallback)
        if score_max == 0: 
            last = state.history[-1]['s']
            return {'pred': last, 'conf': 51, 'type': 'FORCE', 'desc': 'TREND FOLLOW'}

        final = "BIG" if votes_big > votes_small else "SMALL"
        winner = max(votes_big, votes_small)
        avg = winner / score_max # Dynamic Confidence
        
        # [E] DYNAMIC THRESHOLD LOGIC (The 4 Levels)
        req = BASE_THRESHOLD # Level 1-2: 0.55
        tag = "NORMAL"
        
        if state.streak_loss == 2:   # Level 3
            req = RECOVERY_THRESHOLD # 0.70
            tag = "RECOVERY"
        elif state.streak_loss >= 3: # Level 4+
            req = SNIPER_THRESHOLD   # 0.85
            tag = "SNIPER 85%"

        # [F] FINAL DECISION
        if avg >= req:
            if avg > 0.85: tag = "SURESHOT"
            desc = f"V8 ACTION | {tag}"
            if t5 == "REVERSE": desc = "V8 REVERSE LOGIC"
            return {'pred': final, 'conf': round(avg*100, 1), 'type': tag, 'desc': desc}
        
        # Force Bet if Confidence is close (within 5%) AND not in Level 4
        if avg >= (req - 0.05) and state.streak_loss < 3:
             return {'pred': final, 'conf': round(avg*100, 1), 'type': 'RISKY', 'desc': 'FORCED ACTION'}

        return {'pred': 'SKIP', 'conf': round(avg*100, 1), 'type': 'WAIT', 'desc': f'Need {int(req*100)}%'}

# ==========================================
# 🕸️ FLASK UI
# ==========================================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TITAN V8 ACTION</title>
    <meta http-equiv="refresh" content="2">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { background-color: #0f0f13; color: #e0e0e0; font-family: monospace; margin: 0; padding: 20px; }
        .container { max_width: 600px; margin: 0 auto; }
        .header { text-align: center; border-bottom: 2px solid #00f2ff; padding-bottom: 20px; margin-bottom: 20px; }
        .h-title { font-size: 28px; color: #00f2ff; font-weight: bold; }
        .card { background: #1a1a24; border-radius: 10px; padding: 15px; margin-bottom: 15px; }
        .row { display: flex; justify-content: space-between; }
        .stat-val { font-size: 24px; font-weight: bold; }
        .c-green { color: #00ff88; } .c-red { color: #ff0055; } .c-yellow { color: #ffcc00; }
        .bet-box { text-align: center; padding: 20px; border: 1px solid #333; }
        .bet-main { font-size: 40px; font-weight: bold; margin: 10px 0; }
        .bet-type { background: #333; padding: 5px 10px; border-radius: 5px; font-size: 12px; }
        .log-item { padding: 2px 0; border-bottom: 1px solid #222; font-size: 11px; }
        .win-glow { border: 1px solid #00ff88; box-shadow: 0 0 15px #00ff88; }
        .loss-glow { border: 1px solid #ff0055; box-shadow: 0 0 15px #ff0055; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="h-title">TITAN V8 <span style="color:white">ACTION</span></div>
        </div>
        <div class="card row">
            <div style="text-align:center"><div class="stat-val c-green">{{ stats.wins }}</div>WIN</div>
            <div style="text-align:center"><div class="stat-val c-red">{{ stats.losses }}</div>LOSS</div>
            <div style="text-align:center"><div class="stat-val c-yellow">{{ stats.skips }}</div>SKIP</div>
        </div>
        <div class="card bet-box {{ bet_color_class }}">
            <div style="color:#888">ROUND: {{ current_round }}</div>
            {% if active_bet and active_bet.pred != 'SKIP' %}
                <div class="bet-main" style="color: {{ 'cyan' if active_bet.pred == 'BIG' else '#ff00d4' }}">
                    {{ active_bet.pred }}
                </div>
                <div class="bet-type">{{ active_bet.desc }} | {{ active_bet.conf }}%</div>
            {% elif active_bet and active_bet.pred == 'SKIP' %}
                 <div class="bet-main" style="color: #ffcc00; font-size: 30px;">⚠️ WAITING</div>
                 <div class="bet-type">{{ active_bet.desc }}</div>
            {% else %}
                <div class="bet-main" style="color:#444">...</div>
                <div class="bet-type">CALCULATING V8 LOGIC</div>
            {% endif %}
        </div>
        <div class="card" style="height:250px; overflow:hidden">
            {% for log in logs %} <div class="log-item">{{ log }}</div> {% endfor %}
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    bet_class = ""
    if state.last_result:
        if state.last_result['res'] == "WIN": bet_class = "win-glow"
        elif state.last_result['res'] == "LOSS": bet_class = "loss-glow"
    return render_template_string(HTML_TEMPLATE, stats=state.stats, active_bet=state.active_bet, logs=state.logs, current_round=state.current_round, bet_color_class=bet_class)

def run_bot():
    bot = TitanBrain()
    last_id = None
    bot.log("Titan V8 Action Engine Started.")
    
    while True:
        try:
            if not bot.sync_data():
                time.sleep(5) 
                continue
            
            if not state.history: continue
            latest = state.history[-1]
            curr_id = latest['id']
            curr_res = latest['s']
            state.current_round = str(int(curr_id) + 1)

            if last_id and last_id != curr_id:
                if state.active_bet and state.active_bet['pred'] != 'SKIP':
                    if state.active_bet['pred'] == curr_res:
                        state.stats['wins'] += 1
                        state.streak_loss = 0
                        state.last_result = {'res': 'WIN'}
                        bot.log(f"✅ WIN | {curr_id} -> {curr_res}")
                    else:
                        state.stats['losses'] += 1
                        state.streak_loss += 1
                        state.cooldown = 0 
                        state.last_result = {'res': 'LOSS'}
                        bot.log(f"❌ LOSS | {curr_id} -> {curr_res}")
                    state.active_bet = None
                
                pred = bot.analyze()
                if pred:
                    state.active_bet = pred
                    if pred['pred'] == 'SKIP':
                        state.stats['skips'] += 1
                        bot.log(f"⚠️ SKIP: {pred['desc']}")
                    else:
                        bot.log(f"🎯 BET: {pred['pred']} ({pred['conf']}%)")
                
                last_id = curr_id
            
            if last_id is None:
                last_id = curr_id
                pred = bot.analyze()
                if pred: state.active_bet = pred

            time.sleep(2)
        except Exception as e:
            bot.log(f"Err: {e}")
            time.sleep(5)

# Start Thread
t = threading.Thread(target=run_bot)
t.daemon = True
t.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
