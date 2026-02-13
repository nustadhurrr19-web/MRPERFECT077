import requests
import time
import threading
import os
import math
import random
from collections import defaultdict, deque
from flask import Flask, render_template_string, jsonify
import numpy as np

# ==========================================
# CONFIGURATION
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"
FRESH_HISTORY_LIMIT = 300
BANKROLL = 10000.0
app = Flask(__name__)

# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def get_size_val(n): return 1 if int(n) >= 5 else 0
def get_size_str(s): return "BIG" if s == 1 else "SMALL"
def is_prime(n): return n in [2, 3, 5, 7]

# ==========================================
# VISHAL LOGIC: 14 TREND ANALYZERS
# ==========================================
class TrendAnalyzer:
    def basic_trend(self, df, window=10):
        if len(df) < window: return 0.5
        return df.head(window)['s_val'].mean()
        
    def location_trend(self, df, window=10):
        if len(df) < window: return 0.5
        sizes = df.head(window)['s_val'].tolist()
        weights = [0.9**i for i in range(len(sizes))]
        return sum(s * w for s, w in zip(sizes, weights)) / sum(weights)
        
    def big_small_trend(self, df, window=20):
        if len(df) < window: return 0.5
        return df.head(window)['s_val'].mean()
        
    def odd_even_trend(self, df, window=20):
        if len(df) < window: return 0.5
        evens = sum(1 for n in df.head(window)['number'] if n % 2 == 0)
        return 0.6 if evens / window > 0.5 else 0.4
        
    def prime_trend(self, df, window=20):
        if len(df) < window: return 0.5
        primes = sum(1 for n in df.head(window)['number'] if is_prime(n))
        return 0.4 if primes / window > 0.4 else 0.6 
        
    def divide_by3_trend(self, df, window=20, remainder=0):
        if len(df) < window: return 0.5
        count = sum(1 for n in df.head(window)['number'] if n % 3 == remainder)
        return 0.5 + ((count / window) - 0.33)
        
    def five_element_trend(self, df, window=20, element='metal'):
        if len(df) < window: return 0.5
        emap = {'metal': [0,1], 'wood': [2,3], 'water': [4,5], 'fire': [6,7], 'earth': [8,9]}
        targets = emap.get(element, [0,1])
        count = sum(1 for n in df.head(window)['number'] if n in targets)
        is_big_element = any(t >= 5 for t in targets)
        return 0.7 if (count/window > 0.3 and is_big_element) else 0.4
        
    def sum_value_trend(self, df, window=10):
        if len(df) < window: return 0.5
        return np.mean(df.head(window)['number']) / 9.0
        
    def consecutive_trend(self, df, window=20):
        if len(df) < window: return 0.5
        nums = df.head(window)['number'].tolist()
        consec = sum(1 for i in range(len(nums)-1) if abs(nums[i] - nums[i+1]) == 1)
        return 0.5 + ((consec / window) * 0.1)
        
    def mantissa_trend(self, df, window=20):
        if len(df) < window: return 0.5
        return np.mean(df.head(window)['number']) / 9.0
        
    def ranks_trend(self, df, window=20):
        if len(df) < window: return 0.5
        return df.head(window)['s_val'].mean()
        
    def span_trend(self, df, window=10):
        if len(df) < window: return 0.5
        nums = df.head(window)['number'].tolist()
        span = max(nums) - min(nums)
        return 0.6 if span > 5 else 0.4
        
    def new_old_trend(self, df, window=20):
        if len(df) < window * 2: return 0.5
        recent = df.head(window)['s_val'].tolist()
        old = df.iloc[window:window*2]['s_val'].tolist()
        return np.mean(recent) * 0.7 + np.mean(old) * 0.3
        
    def weighted_adjacent_trend(self, df, window=10):
        if len(df) < window: return 0.5
        nums = df.head(window)['s_val'].tolist()
        last = nums[0]
        weights = [0.8**i for i in range(1, len(nums))]
        scores = [(n == last) * w for n, w in zip(nums[1:], weights)]
        return sum(scores) / sum(weights) if weights else 0.5

# ==========================================
# VISHAL LOGIC: OMISSION & PATTERN
# ==========================================
class OmissionAnalyzer:
    def predict_size(self, df):
        if len(df) < 20: return 0.5
        all_nums = df['number'].tolist()
        gaps = {i: 0 for i in range(10)}
        for n in all_nums:
            for k in gaps: gaps[k] += 1
            gaps[n] = 0
        
        due_scores = {k: v for k, v in gaps.items()}
        total_due = sum(due_scores.values())
        if total_due == 0: return 0.5
        
        big_due = sum(v for k, v in due_scores.items() if k >= 5)
        return big_due / total_due

class PatternRecognizer:
    def mirror_strategy(self, sizes, lookback=5):
        if len(sizes) < lookback + 1: return 0.5
        mirror = sizes[:lookback][::-1]
        for i in range(1, len(sizes)-lookback):
            if sizes[i:i+lookback] == mirror:
                if i+lookback < len(sizes):
                    return 0.8 if sizes[i+lookback] == 1 else 0.2
        return 0.5

# ==========================================
# ENGINE ARCHITECTURE (REAL MATH)
# ==========================================
class BaseEngine:
    def __init__(self, name, weight=1.0):
        self.name = name
        self.weight = weight
        self.correct = 0
        self.total = 0
        self.accuracy = 0.5
        
    def update_performance(self, predicted_val, actual_val):
        self.total += 1
        is_correct = (predicted_val > 0.5 and actual_val == 1) or (predicted_val < 0.5 and actual_val == 0)
        if is_correct:
            self.correct += 1
            self.weight = min(2.0, self.weight * 1.05)
        else:
            self.weight = max(0.1, self.weight * 0.95)
        self.accuracy = self.correct / self.total

class TrendEngine(BaseEngine):
    def __init__(self, func, name, weight=1.0):
        super().__init__(f"Trend_{name}", weight)
        self.func = func
    def predict(self, df): return self.func(df)

class QuantumEngine(BaseEngine):
    def __init__(self): super().__init__("Quantum", 1.5)
    def predict(self, df):
        if len(df) < 20: return 0.5
        sizes = df.head(50)['s_val'].tolist()
        mom = sum((s * (0.85**i)) for i, s in enumerate(sizes[:15])) / sum((0.85**i) for i in range(15))
        mean = np.mean(sizes)
        std = np.std(sizes) + 0.001
        z = (sizes[0] - mean) / std
        prob = mom - (0.1 * z) 
        return max(0.1, min(0.9, prob))

class RLEngine(BaseEngine):
    def __init__(self):
        super().__init__("Q-Learning", 1.2)
        self.q_table = defaultdict(lambda: 0.5)
    def predict(self, df):
        if len(df) < 3: return 0.5
        state = tuple(df.head(3)['s_val'].tolist())
        return self.q_table[state]
    def update_q(self, state, actual_val):
        old_q = self.q_table[state]
        reward = 1.0 if actual_val == 1 else 0.0
        self.q_table[state] = old_q + 0.1 * (reward - old_q)

# ==========================================
# TITAN V5 META-LEARNER (THE SUPER BRAIN)
# ==========================================
class UltimateTitanBrain:
    def __init__(self):
        self.history = deque(maxlen=FRESH_HISTORY_LIMIT)
        self.bankroll = BANKROLL
        self.wins = self.losses = self.session_wins = 0
        self.consecutive_losses = self.consecutive_wins = 0
        
        self.last_pred_val = None
        self.last_pred_str = None
        self.last_conf_level = "LOW"
        
        self.ta = TrendAnalyzer()
        self.oa = OmissionAnalyzer()
        self.pa = PatternRecognizer()
        
        self.kalman_prob = 0.5
        self.markov = defaultdict(lambda: {'BIG': 0, 'SMALL': 0})
        
        self.engines = [
            TrendEngine(lambda df: self.ta.basic_trend(df, 10), "Basic10"),
            TrendEngine(lambda df: self.ta.location_trend(df, 15), "Loc15"),
            TrendEngine(lambda df: self.ta.consecutive_trend(df, 20), "Consec"),
            TrendEngine(lambda df: self.ta.span_trend(df, 10), "Span"),
            TrendEngine(lambda df: self.ta.new_old_trend(df, 20), "NewOld"),
            TrendEngine(lambda df: self.ta.weighted_adjacent_trend(df, 10), "Adj"),
            TrendEngine(lambda df: self.oa.predict_size(df), "Omission", weight=1.5),
            TrendEngine(lambda df: self.pa.mirror_strategy(df['s_val'].tolist()), "Mirror", weight=1.2),
            QuantumEngine(),
            RLEngine()
        ]

    def get_size_val(self, n): return 1 if int(n) >= 5 else 0
    def get_size_str(self, s): return "BIG" if s == 1 else "SMALL"

    def sync_data(self):
        try:
            all_data = []
            # FORCE FETCH 3 PAGES (300 ROUNDS) TO BYPASS SAFETY LOCK
            for p in range(1, 20): 
                r = requests.get(API_URL, params={"size": "100", "pageNo": str(p)}, timeout=5)
                if r.status_code == 200:
                    data = r.json().get('data', {}).get('list', [])
                    if not data: break
                    all_data.extend(data)
            
            if not all_data: return False
            
            all_data.sort(key=lambda x: int(x['issueNumber']))
            self.history.clear()
            for item in all_data[-FRESH_HISTORY_LIMIT:]:
                n = int(item['number'])
                self.history.append({
                    'n': n, 'id': str(item['issueNumber']), 's_val': self.get_size_val(n)
                })
            self.train_markov()
            return True
        except Exception as e:
            print(f"Sync error: {e}")
        return False

    def train_markov(self):
        self.markov.clear()
        hist_list = list(self.history)
        for i in range(3, len(hist_list)):
            ps = tuple(hist_list[j]['s_val'] for j in range(i-3, i))
            rs = 'BIG' if hist_list[i]['s_val'] == 1 else 'SMALL'
            self.markov[ps][rs] += 1

    def analyze_meta(self):
        # LOWERED SAFETY LOCK: Only needs 15 rounds of data now!
        if len(self.history) < 15: return 0.5, 0.0
        
        import pandas as pd
        df = pd.DataFrame([{'number': x['n'], 's_val': x['s_val']} for x in reversed(self.history)])
        
        total_weight = 0
        weighted_prob = 0
        
        for e in self.engines:
            prob = e.predict(df)
            w = e.weight
            weighted_prob += (prob * w)
            total_weight += w
            
        meta_prob = weighted_prob / total_weight if total_weight > 0 else 0.5
        
        hist_list = list(self.history)
        last3 = tuple(hist_list[-3:][j]['s_val'] for j in range(3))
        markov_prob = 0.5
        if last3 in self.markov:
            s = self.markov[last3]
            tot = sum(s.values())
            if tot > 0: markov_prob = s['BIG']/tot
            
        final_prob = (meta_prob * 0.5) + (markov_prob * 0.3) + (self.kalman_prob * 0.2)
        
        # BOOSTED SENSITIVITY: Multiplied by 25 to force strong bets and break ties
        strength = min(4.0, abs(final_prob - 0.5) * 25) 
        return final_prob, strength

    def feedback_loop(self, actual_val):
        self.kalman_prob += 0.15 * (actual_val - self.kalman_prob)
        import pandas as pd
        df = pd.DataFrame([{'number': x['n'], 's_val': x['s_val']} for x in reversed(self.history)])
        for e in self.engines:
            pred_val = e.predict(df)
            e.update_performance(pred_val, actual_val)
            if isinstance(e, RLEngine) and len(self.history) >= 3:
                state = tuple([x['s_val'] for x in list(self.history)[-3:]])
                e.update_q(state, actual_val)

    def get_bet_size(self, level):
        factors = {"SURESHOT": 0.05, "HIGH": 0.03, "GOOD": 0.01, "LOW": 0}
        return self.bankroll * factors.get(level, 0)

# ==========================================
# WORKER PROCESS
# ==========================================
bot = UltimateTitanBrain()
state = {
    "period": "...", "pred": "--", "type": "V5 META", "level": "WAIT",
    "wins": 0, "losses": 0, "session": 0, "history": [],
    "bankroll": BANKROLL, "bet_size": 0, "streak": "NORMAL",
    "data_count": 0 # NEW DATA METER STATE
}

def worker():
    last_id = None
    while True:
        try:
            if not bot.history: 
                bot.sync_data()
            
            # ALWAYS UPDATE DATA METER
            state["data_count"] = len(bot.history)

            r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=4)
            if r.status_code != 200:
                time.sleep(2); continue

            data = r.json().get('data', {}).get('list', [])
            if not data: time.sleep(2); continue

            d = data[0]
            cid = str(d['issueNumber'])
            n = int(d['number'])

            if cid != last_id:
                real_val = bot.get_size_val(n)
                real_str = bot.get_size_str(real_val)
                status = "WAIT"
                
                if bot.last_pred_str and bot.last_pred_str != "SKIP":
                    bot.feedback_loop(real_val)
                    
                    bet_amt = state.get('bet_size', 0)
                    if bot.last_pred_str == real_str:
                        bot.bankroll += bet_amt
                        bot.wins += 1; bot.session_wins += 1
                        bot.consecutive_losses = 0; bot.consecutive_wins += 1
                        status = "WIN"
                    else:
                        bot.bankroll -= bet_amt
                        bot.losses += 1
                        bot.consecutive_losses += 1; bot.consecutive_wins = 0
                        status = "LOSS"

                state["history"].insert(0, {"p": cid[-4:], "r": real_str, "s": status, "l": bot.last_conf_level})
                state["history"] = state["history"][:15]

                bot.history.append({'n': n, 'id': cid, 's_val': real_val})
                bot.train_markov()
                
                # Update data meter after append
                state["data_count"] = len(bot.history)

                final_prob, raw_score = bot.analyze_meta()
                pred_str = "BIG" if final_prob > 0.5 else "SMALL"
                
                streak_level = min(bot.consecutive_losses, 2)
                req_score = [1.2, 1.4, 1.0][streak_level]
                target_level = ["GOOD", "HIGH", "SURESHOT"][streak_level]
                streak_status = ["NORMAL", "RECOVER L1", "MAX BET L2"][streak_level]

                if raw_score >= req_score:
                    final_level = "SURESHOT" if raw_score >= 3.0 else target_level
                    bet_size = bot.get_bet_size(final_level)
                    bot.last_pred_str = pred_str
                    bot.last_conf_level = final_level
                    
                    state.update({
                        "period": str(int(cid) + 1), "pred": pred_str, "type": "V5 NEURAL", 
                        "level": final_level, "wins": bot.wins, "losses": bot.losses,
                        "session": bot.session_wins, "streak": streak_status,
                        "bankroll": round(bot.bankroll, 0), "bet_size": round(bet_size, 0)
                    })
                else:
                    bot.last_pred_str = "SKIP"
                    bot.last_conf_level = "WAIT"
                    state.update({
                        "period": str(int(cid) + 1), "pred": "SKIP", "type": "ANALYZING",
                        "level": "WAIT", "wins": bot.wins, "losses": bot.losses,
                        "session": bot.session_wins, "streak": streak_status,
                        "bankroll": round(bot.bankroll, 0), "bet_size": 0
                    })

                last_id = cid
            time.sleep(1.5)

        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(3)

threading.Thread(target=worker, daemon=True).start()

# ==========================================
# AP.PY V5 HTML UI - WITH LIVE DATA METER
# ==========================================
HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TITAN V5.0 - ULTIMATE HYBRID</title>
    <link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #000; --card: #111; --text: #fff; --green: #00e676; --red: #ff1744; --blue: #2979ff; --yellow: #ffeb3b; --orange: #ff9100; --purple: #d500f9; --cyan: #00e5ff; }
        body { background: var(--bg); color: var(--text); font-family: 'Oswald', sans-serif; margin: 0; padding: 15px; text-align: center; text-transform: uppercase; }
        .container { max-width: 500px; margin: 0 auto; }
        .card { background: var(--card); border: 1px solid #222; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .score-row { display: flex; justify-content: space-between; font-size: 20px; margin-bottom: 5px; border-bottom: 1px solid #222; padding-bottom: 10px; }
        .w { color: var(--green); } .l { color: var(--red); }
        .streak { font-size: 12px; color: var(--purple); font-weight: bold; }
        .data-meter { font-size: 13px; color: #888; margin-top: 8px; font-weight: bold; letter-spacing: 1px; }
        .data-val { color: var(--cyan); text-shadow: 0 0 5px rgba(0, 229, 255, 0.4); }
        .pred-box { margin: 20px 0; min-height: 120px; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        .type-badge { font-size: 14px; color: #666; letter-spacing: 2px; margin-bottom: 5px; }
        .val-BIG { color: var(--blue); font-size: 80px; font-weight: bold; text-shadow: 0 0 20px rgba(41,121,255,0.4); }
        .val-SMALL { color: var(--orange); font-size: 80px; font-weight: bold; text-shadow: 0 0 20px rgba(255,145,0,0.4); }
        .val-SKIP { font-size: 40px; color: #555; animation: pulse 2s infinite; }
        .conf-badge { padding: 8px 16px; border-radius: 6px; font-size: 18px; display: inline-block; color: #000; font-weight: bold; }
        .lvl-WAIT { background: #333; color: #777; }
        .lvl-GOOD { background: var(--blue); }
        .lvl-HIGH { background: var(--green); }
        .lvl-SURESHOT { background: var(--purple); color: #fff; animation: pulse 0.5s infinite; }
        .bankroll { font-size: 18px; color: var(--yellow); }
        .row { display: flex; justify-content: space-between; padding: 12px; background: #0a0a0a; border-radius: 6px; margin-bottom: 5px; align-items: center; border-left: 4px solid #333; }
        .row.WIN { border-left-color: var(--green); } .row.LOSS { border-left-color: var(--red); } .row.DONE { border-left-color: var(--yellow); }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="score-row">
                <span>TITAN V5.0 MEGA BRAIN</span>
                <span id="bankroll" class="bankroll">₹10,000</span>
            </div>
            <div><span class="w" id="w">W:0</span> <span class="l" id="l">L:0</span></div>
            <div style="font-size:12px;color:#666;">
                PERIOD <span id="p" style="color:#fff;">...</span> | BET ₹<span id="bet">0</span>
            </div>
            <div class="streak" id="streak">NORMAL</div>
            <div class="data-meter">
                📊 LIVE DATA LOADED: <span id="data_count" class="data-val">0</span> / 300
            </div>
        </div>
        
        <div class="card">
            <div class="pred-box">
                <div id="type" class="type-badge">DATA FUSION...</div>
                <div id="pred" class="val-BIG">--</div>
                <div style="margin-top:15px;">
                    <span id="lvl" class="conf-badge lvl-WAIT">WAIT</span>
                </div>
            </div>
        </div>
        
        <div class="card">
            <div style="text-align:left;color:#666;font-size:12px;margin-bottom:10px;">RECENT RESULTS</div>
            <div id="hist"></div>
        </div>
    </div>
    
    <script>
        setInterval(() => {
            fetch('/api/status').then(r => r.json()).then(d => {
                document.getElementById('p').innerText = d.period;
                document.getElementById('w').innerText = `W:${d.wins}`;
                document.getElementById('l').innerText = `L:${d.losses}`;
                document.getElementById('bankroll').innerText = `₹${d.bankroll}`;
                document.getElementById('bet').innerText = d.bet_size;
                document.getElementById('streak').innerText = d.streak;
                
                // UPDATE DATA METER UI
                document.getElementById('data_count').innerText = d.data_count;
                
                let pEl = document.getElementById('pred');
                let tEl = document.getElementById('type');
                let lEl = document.getElementById('lvl');
                
                if (d.pred === 'SKIP') {
                    tEl.innerText = 'WAITING FOR META SIGNAL';
                    pEl.innerText = 'SKIPPING';
                    pEl.className = 'val-SKIP';
                    lEl.innerText = 'WAIT';
                    lEl.className = 'conf-badge lvl-WAIT';
                } else {
                    tEl.innerText = `${d.type} ${d.streak}`;
                    pEl.innerText = d.pred;
                    pEl.className = `val-${d.pred}`;
                    lEl.innerText = d.level;
                    lEl.className = `conf-badge lvl-${d.level}`;
                }
                
                document.getElementById('hist').innerHTML = d.history.map(h => {
                    let cls = h.s === 'WIN' ? 'WIN' : h.s === 'LOSS' ? 'LOSS' : 'DONE';
                    return `<div class="row ${cls}">
                        <span style="color:#666;">${h.p}</span>
                        <span style="color:#eee;">${h.r}</span>
                        <span style="color:${cls==='WIN'?'#00e676':cls==='LOSS'?'#ff1744':'#ffeb3b'}">${h.s}</span>
                        <span style="color:#666;">${h.l}</span>
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
    # Auto-install pandas if missing (Fixed Syntax for Windows/PC)
    try:
        import pandas
    except ImportError:
        print("Pandas not found. Installing now...")
        os.system("pip install pandas")
        import pandas
        
    port = int(os.environ.get('PORT', 5011))
    app.run(host='0.0.0.0', port=port, debug=False)
