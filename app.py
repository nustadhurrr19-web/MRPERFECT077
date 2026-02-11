import requests
import time
import threading
import datetime
import os
from collections import Counter
from flask import Flask, render_template_string

# ==========================================
# ⚙️ TITAN V5 CONFIGURATION (CLOUD + BRAIN)
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"

# BALANCED LOGIC SETTINGS (V3.5 Brain)
BASE_THRESHOLD = 0.60       # 60% Confidence to Bet (Turbo Mode)
SNIPER_THRESHOLD = 0.85     # 85% for Recovery Bets
MIN_HISTORY_MATCHES = 6     # Need 6 past matches to trust a pattern
VOLATILITY_LIMIT = 12       # Allow 12 flips in last 15 rounds (Relaxed Safety)

# ==========================================
# 📊 SHARED STATE STORE
# ==========================================
class GameState:
    def __init__(self):
        self.history = []
        self.active_bet = None 
        self.last_result = None 
        self.stats = {'wins': 0, 'losses': 0, 'skips': 0}
        self.logs = []          
        self.current_round = "WAITING"
        self.streak_loss = 0    # Track consecutive losses
        self.cooldown = 0       # Track cooldown rounds

state = GameState()

# ==========================================
# 🧠 TITAN V5 LOGIC ENGINE (CONSENSUS + REVERSE)
# ==========================================
class TitanBrain:
    def get_size(self, n): 
        return "BIG" if int(n) >= 5 else "SMALL"

    def sync_data(self):
        try:
            all_data = []
            # Fetch 20 Pages (400 Rounds) for Deep Analysis
            for p in range(1, 21): 
                r = requests.get(API_URL, params={"size": "20", "pageNo": str(p)}, timeout=4)
                if r.status_code == 200:
                    data = r.json().get('data', {}).get('list', [])
                    all_data.extend(data)
            
            all_data.sort(key=lambda x: int(x['issueNumber']))
            state.history = [{
                'n': int(item['number']), 
                's': self.get_size(item['number']), 
                'id': str(item['issueNumber'])
            } for item in all_data]
            return True
        except Exception as e:
            return False

    def log(self, msg):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        state.logs.insert(0, f"[{timestamp}] {msg}")
        if len(state.logs) > 50: state.logs.pop()

    # --- 1. VOLATILITY CHECK ---
    def check_market_state(self):
        if len(state.history) < 20: return "NORMAL"
        subset = state.history[-15:]
        flips = 0
        for i in range(1, len(subset)):
            if subset[i]['s'] != subset[i-1]['s']:
                flips += 1
        
        if flips >= VOLATILITY_LIMIT: return "DANGEROUS"
        return "NORMAL"

    # --- 2. PATTERN ENGINE (With REVERSE Logic) ---
    def get_pattern_signal(self, depth):
        if len(state.history) < depth + 1: return None, 0, "NONE"
        
        current_seq = [x['s'] for x in state.history[-depth:]]
        matches = []
        
        for i in range(len(state.history) - (depth + 1)):
            window = [x['s'] for x in state.history[i : i+depth]]
            if window == current_seq:
                outcome = state.history[i+depth]['s']
                matches.append(outcome)
        
        if len(matches) < MIN_HISTORY_MATCHES: 
            return None, 0, "LOW_DATA"

        counts = Counter(matches)
        top_res = counts.most_common(1)[0]
        confidence = top_res[1] / len(matches)
        
        # REVERSE LOGIC: If a pattern is super unlucky (<20%), bet OPPOSITE
        if confidence < 0.20:
             # Example: Big is 10%, so Small is 90%
             reverse_pred = "SMALL" if top_res[0] == "BIG" else "BIG"
             return reverse_pred, (1.0 - confidence), "REVERSE_PATTERN"
             
        return top_res[0], confidence, "PATTERN"

    # --- 3. NUMBER BIAS ENGINE ---
    def get_number_bias(self, target_num):
        matches = [x for x in state.history[:-1] if x['n'] == target_num]
        if len(matches) < 4: return None, 0.0

        next_indices = [state.history.index(m) + 1 for m in matches if state.history.index(m) + 1 < len(state.history)]
        outcomes = [state.history[i]['s'] for i in next_indices]
        if not outcomes: return None, 0.0
        
        counts = Counter(outcomes)
        top_res = counts.most_common(1)[0]
        confidence = top_res[1] / len(outcomes)
        return top_res[0], confidence

    # --- MASTER ANALYSIS (V5) ---
    def analyze(self):
        # [A] COOLDOWN & SAFETY
        if state.cooldown > 0:
            state.cooldown -= 1
            return None # Skip (Cooldown active)

        if self.check_market_state() == "DANGEROUS":
            # In V5 Cloud, we log this but don't always skip unless strictly needed
            # For now, we will SKIP to save money as requested
            return {'pred': 'SKIP', 'conf': 0, 'type': 'WARNING', 'desc': 'MARKET TOO CHOPPY'}

        # [B] GATHER SIGNALS
        p5, c5, t5 = self.get_pattern_signal(5) # Deep Pattern
        p4, c4, t4 = self.get_pattern_signal(4) # Standard Pattern
        
        last_digit = state.history[-1]['n']
        n_pred, n_conf = self.get_number_bias(last_digit) # Number Bias

        # [C] VOTING SYSTEM
        votes_big = 0
        votes_small = 0
        max_possible_score = 0
        
        # Engine 1: Deep Pattern (Weight 2.0)
        if p5: 
            w = 2.0
            max_possible_score += w
            if p5 == "BIG": votes_big += c5 * w
            else: votes_small += c5 * w
            
        # Engine 2: Standard Pattern (Weight 1.5)
        if p4:
            w = 1.5
            max_possible_score += w
            if p4 == "BIG": votes_big += c4 * w
            else: votes_small += c4 * w

        # Engine 3: Number Bias (Weight 1.0)
        if n_pred:
            w = 1.0
            max_possible_score += w
            if n_pred == "BIG": votes_big += n_conf * w
            else: votes_small += n_conf * w

        # [D] FINAL CALCULATION
        if max_possible_score == 0: return None

        final_pred = "BIG" if votes_big > votes_small else "SMALL"
        winner_score = max(votes_big, votes_small)
        
        # DYNAMIC CONFIDENCE: Only divide by active engines
        avg_confidence = winner_score / max_possible_score
        
        # [E] CONFLICT CHECK
        if p5 and n_pred and p5 != n_pred and n_conf > 0.75:
             return {'pred': 'SKIP', 'conf': int(avg_confidence*100), 'type': 'CONFLICT', 'desc': f'Pat({p5}) != Num({n_pred})'}

        # [F] THRESHOLDS (Dynamic)
        req_strength = BASE_THRESHOLD # 0.60
        tag = "NORMAL"
        
        if state.streak_loss >= 2:
            req_strength = SNIPER_THRESHOLD # 0.85 (Recovery Mode)
            tag = "RECOVERY"
        elif state.streak_loss == 1:
            req_strength += 0.05
            tag = "CAUTIOUS"

        if avg_confidence >= req_strength:
            if avg_confidence > 0.85: tag = "SURESHOT"
            desc_str = f"V5 CONSENSUS | {tag}"
            if t5 == "REVERSE_PATTERN": desc_str = "V5 REVERSE LOGIC"
            
            return {'pred': final_pred, 'conf': round(avg_confidence*100, 1), 'type': tag, 'desc': desc_str}
        
        return None # Too weak

# ==========================================
# 🕸️ FLASK WEB UI (TITAN V5 DASHBOARD)
# ==========================================
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TITAN V5 ULTIMATE</title>
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
            <div class="h-title">TITAN V5 <span style="color:white">ULTIMATE</span></div>
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
                 <div class="bet-main" style="color: #ffcc00; font-size: 30px;">⚠️ SKIP</div>
                 <div class="bet-type">{{ active_bet.desc }}</div>
            {% else %}
                <div class="bet-main" style="color:#444">...</div>
                <div class="bet-type">CALCULATING V5 LOGIC</div>
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

# ==========================================
# 🔄 BOT THREAD (BACKEND)
# ==========================================
def run_bot():
    bot = TitanBrain()
    last_id = None
    
    bot.log("Titan V5 Ultimate Engine Started.")
    
    while True:
        try:
            # 1. Sync
            if not bot.sync_data():
                time.sleep(2)
                continue
            
            if not state.history: continue
            
            latest = state.history[-1]
            curr_id = latest['id']
            curr_res = latest['s']
            state.current_round = str(int(curr_id) + 1)

            # 2. Result Check
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
                        state.cooldown = 1 # Safety Cooldown
                        state.last_result = {'res': 'LOSS'}
                        bot.log(f"❌ LOSS | {curr_id} -> {curr_res}")
                    state.active_bet = None
                
                # 3. Analyze Next
                pred = bot.analyze()
                if pred:
                    state.active_bet = pred
                    if pred['pred'] == 'SKIP':
                        state.stats['skips'] += 1
                        bot.log(f"⚠️ SKIP: {pred['desc']}")
                    else:
                        bot.log(f"🎯 BET: {pred['pred']} ({pred['conf']}%)")
                
                last_id = curr_id
            
            # Initial Load
            if last_id is None:
                last_id = curr_id
                pred = bot.analyze()
                if pred: state.active_bet = pred

            time.sleep(2)
        except Exception as e:
            bot.log(f"Err: {e}")
            time.sleep(2)

# ==========================================
# 🚀 LAUNCHER
# ==========================================
t = threading.Thread(target=run_bot)
t.daemon = True
t.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
