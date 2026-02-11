import requests
import time
import threading
import datetime
import os
import math
from collections import Counter
from flask import Flask, render_template_string

# ==========================================
# ⚙️ TITAN V10 CONFIGURATION (GEMINI HYBRID)
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"

# LOGIC THRESHOLDS
BASE_CONFIDENCE = 0.55      # Level 1: Normal Bet
STRONG_CONFIDENCE = 0.70    # Level 2: Strong Bet
SNIPER_CONFIDENCE = 0.85    # Level 3: Sureshot
ENTROPY_THRESHOLD = 0.98    # Filter: If Entropy > 0.98, Market is too random (SKIP)

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
# 🧠 TITAN BRAIN V10 (ML + GEMINI LOGIC)
# ==========================================
class TitanBrain:
    def get_size(self, n): 
        return "BIG" if int(n) >= 5 else "SMALL"

    def log(self, msg):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}", flush=True) 
        state.logs.insert(0, f"[{timestamp}] {msg}")
        if len(state.logs) > 60: state.logs.pop()

    def sync_data(self):
        try:
            all_data = []
            self.log("📡 Connecting to Gemini Neural Cloud...")
            
            # FAST SYNC (20 Pages / 400 Rounds)
            for p in range(1, 21): 
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

    # --- 1. GEMINI LOGIC: SHANNON ENTROPY (Chaos Detection) ---
    def check_entropy(self):
        # Calculate entropy of last 20 rounds to measure randomness
        if len(state.history) < 20: return 0.5
        recent = [x['s'] for x in state.history[-20:]]
        counts = Counter(recent)
        total = len(recent)
        entropy = 0
        for count in counts.values():
            p = count / total
            if p > 0: entropy -= p * math.log2(p)
        
        # Max entropy for binary outcome is 1.0. 
        # If entropy > 0.98, it means outcomes are almost perfectly 50/50 (Pure Chaos).
        return entropy

    # --- 2. GEMINI LOGIC: MARKOV CHAINS (Transition Probability) ---
    def get_markov_signal(self):
        if len(state.history) < 50: return None, 0, "TRAINING"
        
        last_res = state.history[-1]['s'] # e.g., "BIG"
        
        # Count what usually happens after "BIG"
        next_outcomes = []
        for i in range(len(state.history) - 1):
            if state.history[i]['s'] == last_res:
                next_outcomes.append(state.history[i+1]['s'])
        
        if not next_outcomes: return None, 0, "NO_DATA"
        
        count = Counter(next_outcomes)
        top = count.most_common(1)[0]
        conf = top[1] / len(next_outcomes)
        
        return top[0], conf, f"MARKOV ({last_res}->{top[0]})"

    # --- 3. GEMINI LOGIC: Z-SCORE (Mean Reversion) ---
    def get_z_score_signal(self):
        # Check imbalance in last 30 rounds
        if len(state.history) < 30: return None, 0
        
        recent = [1 if x['s'] == "BIG" else -1 for x in state.history[-30:]]
        running_sum = sum(recent)
        
        # If running sum is very positive, BIG is overbought -> Bet SMALL
        # If running sum is very negative, SMALL is overbought -> Bet BIG
        
        if running_sum > 8: # High excess of BIG
            return "SMALL", 0.65, "MEAN REVERSION"
        elif running_sum < -8: # High excess of SMALL
            return "BIG", 0.65, "MEAN REVERSION"
        
        return None, 0, "BALANCED"

    # --- 4. ML ENGINE (k-NN) ---
    def get_ml_signal(self):
        if len(state.history) < 50: return None, 0, "TRAINING"
        current_vec = [1 if x['s'] == "BIG" else 0 for x in state.history[-8:]]
        similarities = []
        for i in range(len(state.history) - 20):
            past_vec = [1 if x['s'] == "BIG" else 0 for x in state.history[i : i+8]]
            diff = sum(abs(c - p) for c, p in zip(current_vec, past_vec))
            if diff <= 1:
                similarities.append(state.history[i+8]['s'])
        
        if not similarities: return None, 0, "NO_MATCH"
        top = Counter(similarities).most_common(1)[0]
        return top[0], top[1] / len(similarities), "ML (k-NN)"

    # --- MASTER ANALYZE V10 ---
    def analyze(self):
        if state.cooldown > 0:
            state.cooldown -= 1
            return None 

        # [A] SAFETY CHECK: ENTROPY
        entropy = self.check_entropy()
        if entropy > ENTROPY_THRESHOLD:
            # Market is too random. Gemini says wait.
            # But if in Recovery Mode, we might take risks.
            if state.streak_loss < 2:
                return {'pred': 'SKIP', 'conf': 0, 'type': 'WAIT', 'desc': f'HIGH CHAOS ({round(entropy,2)})'}

        # [B] GATHER SIGNALS
        markov_pred, markov_conf, markov_desc = self.get_markov_signal()
        ml_pred, ml_conf, ml_desc = self.get_ml_signal()
        z_pred, z_conf, z_desc = self.get_z_score_signal()
        
        # [C] VOTING SYSTEM (Weighted)
        votes_big = 0.0
        votes_small = 0.0
        total_weight = 0.0

        # Markov Chain (Weight 2.0) - High reliability for short term
        if markov_pred:
            w = 2.0; total_weight += w
            if markov_pred == "BIG": votes_big += markov_conf * w
            else: votes_small += markov_conf * w
            
        # ML Engine (Weight 2.0) - Pattern matching
        if ml_pred:
            w = 2.0; total_weight += w
            if ml_pred == "BIG": votes_big += ml_conf * w
            else: votes_small += ml_conf * w
            
        # Z-Score (Weight 1.5) - Statistical Balance
        if z_pred:
            w = 1.5; total_weight += w
            if z_pred == "BIG": votes_big += z_conf * w
            else: votes_small += z_conf * w

        # [D] FINAL CALCULATION
        if total_weight == 0:
             # Fallback
             last = state.history[-1]['s']
             pred = "SMALL" if last == "BIG" else "BIG"
             return {'pred': pred, 'conf': 52, 'type': 'FORCE', 'desc': 'ZIGZAG FALLBACK'}

        final_pred = "BIG" if votes_big > votes_small else "SMALL"
        score = max(votes_big, votes_small)
        avg_conf = score / total_weight

        # [E] TAGGING & THRESHOLDS
        tag = "NORMAL"
        desc = "V10 HYBRID"

        # Check Agreements
        agreements = 0
        if markov_pred == final_pred: agreements += 1
        if ml_pred == final_pred: agreements += 1
        if z_pred == final_pred: agreements += 1

        # LEVEL 3: SURESHOT
        if avg_conf > SNIPER_CONFIDENCE or agreements == 3:
            tag = "SURESHOT"
            desc = "FULL CONSENSUS"
        
        # LEVEL 2: STRONG
        elif avg_conf > STRONG_CONFIDENCE:
            tag = "STRONG"
            desc = f"AGREEMENT ({agreements}/3)"
        
        # LEVEL 1: ACTION
        elif avg_conf > BASE_CONFIDENCE:
            tag = "ACTION"
            desc = markov_desc

        # [F] RECOVERY OVERRIDE
        if state.streak_loss >= 2:
            if avg_conf < 0.75: 
                return {'pred': 'SKIP', 'conf': 0, 'type': 'WAIT', 'desc': 'RECOVERY SCANNING'}
            tag = "RECOVERY"
            desc = "SNIPER LOCK"

        return {'pred': final_pred, 'conf': round(avg_conf*100, 1), 'type': tag, 'desc': desc}

# ==========================================
# 🕸️ FLASK UI (GEMINI THEME)
# ==========================================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TITAN V10 GEMINI</title>
    <meta http-equiv="refresh" content="2">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { background-color: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 20px; }
        .container { max_width: 600px; margin: 0 auto; border: 1px solid #30363d; padding: 20px; border-radius: 10px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        .header { text-align: center; border-bottom: 1px solid #30363d; padding-bottom: 20px; margin-bottom: 20px; }
        .h-title { font-size: 28px; background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: bold; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
        .row { display: flex; justify-content: space-between; }
        .stat-val { font-size: 24px; font-weight: bold; }
        .c-green { color: #2ea043; } .c-red { color: #da3633; } .c-yellow { color: #d29922; }
        .bet-box { text-align: center; padding: 20px; border: 1px solid #30363d; background: #0d1117; }
        .bet-main { font-size: 48px; font-weight: bold; margin: 15px 0; letter-spacing: 1px; }
        .bet-type { background: #21262d; color: #8b949e; padding: 4px 12px; border-radius: 20px; font-size: 12px; display: inline-block; border: 1px solid #30363d; }
        .log-item { padding: 4px 0; border-bottom: 1px solid #21262d; font-size: 11px; color: #8b949e; font-family: monospace; }
        
        .type-SURESHOT { background: rgba(218, 54, 51, 0.2); color: #ff7b72; border: 1px solid #da3633; }
        .type-RECOVERY { background: rgba(46, 160, 67, 0.2); color: #3fb950; border: 1px solid #2ea043; }
        
        .win-glow { border: 1px solid #2ea043; box-shadow: 0 0 20px rgba(46, 160, 67, 0.2); }
        .loss-glow { border: 1px solid #da3633; box-shadow: 0 0 20px rgba(218, 54, 51, 0.2); }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="h-title">TITAN V10 <span style="font-weight:300">GEMINI</span></div>
            <div style="font-size: 11px; color: #8b949e; margin-top:5px;">MARKOV CHAINS • ENTROPY FILTER • ML HYBRID</div>
        </div>
        
        <div class="card row">
            <div style="text-align:center"><div class="stat-val c-green">{{ stats.wins }}</div>WIN</div>
            <div style="text-align:center"><div class="stat-val c-red">{{ stats.losses }}</div>LOSS</div>
            <div style="text-align:center"><div class="stat-val c-yellow">{{ stats.skips }}</div>SKIP</div>
        </div>

        <div class="card bet-box {{ bet_color_class }}">
            <div style="color:#8b949e; font-size: 12px;">ROUND: {{ current_round }}</div>
            {% if active_bet and active_bet.pred != 'SKIP' %}
                <div class="bet-main" style="color: {{ '#58a6ff' if active_bet.pred == 'BIG' else '#d29922' }}">
                    {{ active_bet.pred }}
                </div>
                <div class="bet-type type-{{ active_bet.type }}">{{ active_bet.desc }} | {{ active_bet.conf }}%</div>
            {% elif active_bet and active_bet.pred == 'SKIP' %}
                 <div class="bet-main" style="color: #8b949e; font-size: 24px;">ANALYZING...</div>
                 <div class="bet-type">{{ active_bet.desc }}</div>
            {% else %}
                <div class="bet-main" style="color:#30363d">...</div>
                <div class="bet-type">INITIALIZING NEURAL NET</div>
            {% endif %}
        </div>

        <div class="card" style="height:200px; overflow:hidden">
            <div style="color: #8b949e; border-bottom: 1px solid #21262d; margin-bottom: 5px; font-size:11px;">SYSTEM LOGS</div>
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
    bot.log("Titan V10 Gemini Engine Starting...")
    
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
