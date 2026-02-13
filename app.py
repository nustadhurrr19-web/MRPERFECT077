import requests
import time
import threading
import os
import csv
from collections import defaultdict, deque
from flask import Flask, render_template_string, jsonify
from datetime import datetime
import numpy as np

# ==========================================
# ⚙️ CONFIGURATION - FRESH DATA ONLY
# ==========================================
API_URL = "https://api-iok6.onrender.com/api/get_history"
FRESH_HISTORY_LIMIT = 200
BANKROLL = 10000.0
app = Flask(__name__)

# ==========================================
# 🧠 TITAN BRAIN V3.1 - PRODUCTION READY
# ==========================================
class TitanBrain:
    def __init__(self):
        self.history = deque(maxlen=FRESH_HISTORY_LIMIT)
        self.bankroll = BANKROLL
        self.wins = 0
        self.losses = 0
        self.session_wins = 0
        self.consecutive_losses = 0
        self.last_pred = None
        self.last_type = "SIZE"
        self.last_conf = "LOW"
        
        # ENSEMBLE ENGINES
        self.markov_size = defaultdict(lambda: {'BIG': 0, 'SMALL': 0})
        self.markov_color = defaultdict(lambda: {'RED': 0, 'GREEN': 0})
        self.pat_size = self.get_patterns()
        
        # KALMAN FILTER
        self.kalman_size_prob = 0.5
        self.kalman_color_prob = 0.5
        
        # PERFORMANCE
        self.score_performance = defaultdict(lambda: {'wins': 0, 'total': 0})

    def get_patterns(self):
        return {
            "11111": 1, "00000": 0, "10101": 0, "01010": 1,
            "11001": 0, "00110": 1, "11100": 0, "00011": 1,
            "10010": 1, "01101": 0, "11011": 0, "00100": 1,
            "11101": 0, "00010": 1, "10001": 0, "01110": 1
        }

    def get_size_val(self, n):
        return 1 if int(n) >= 5 else 0

    def get_size_str(self, s):
        return "BIG" if s == 1 else "SMALL"

    def get_color_val(self, n):
        n = int(n)
        return 1 if n in [1, 3, 5, 7, 9] else 0

    def get_color_str(self, c):
        return "GREEN" if c == 1 else "RED"

    def get_bet_size(self, level):
        factors = {"SURESHOT": 0.03, "HIGH": 0.02, "GOOD": 0.01, "LOW": 0}
        return self.bankroll * factors.get(level, 0)

    def analyze_ensemble(self, mode):
        hist_list = list(self.history)
        if len(hist_list) < 5:
            return 0, 1.0

        # Pattern match
        seq = ''.join(str(x[mode]) for x in hist_list[-5:])
        p1 = self.pat_size.get(seq, 0.5)

        # Markov 3-gram
        last3 = tuple(hist_list[-3:][j][mode] for j in range(3))
        target_markov = self.markov_size if mode == 's_val' else self.markov_color
        p2 = 0.5
        if last3 in target_markov:
            s = target_markov[last3]
            tot = sum(s.values())
            if tot > 0:
                p2 = s['BIG']/tot if mode == 's_val' else s['GREEN']/tot

        # Momentum
        recent = [x[mode] for x in hist_list[-3:]]
        p3 = sum(recent) / 3.0

        # Ensemble prediction
        ensemble_pred = (p1 * 0.4 + p2 * 0.4 + p3 * 0.2)
        strength = min(4.0, abs(ensemble_pred - 0.5) * 8)
        return 1 if ensemble_pred > 0.5 else 0, strength

    def update_kalman(self, mode, actual_val):
        gain = 0.15
        if mode == 's_val':
            error = actual_val - self.kalman_size_prob
            self.kalman_size_prob += gain * error
        else:
            error = actual_val - self.kalman_color_prob
            self.kalman_color_prob += gain * error

    def sync_data(self):
        try:
            all_data = []
            r = requests.get(API_URL, params={"size": str(FRESH_HISTORY_LIMIT), "pageNo": "1"}, timeout=5)
            if r.status_code == 200:
                data = r.json().get('data', {}).get('list', [])
                if len(data) > 100:
                    all_data = data

            if not all_
                for p in range(1, 11):
                    r = requests.get(API_URL, params={"size": "50", "pageNo": str(p)}, timeout=3)
                    if r.status_code == 200:
                        data = r.json().get('data', {}).get('list', [])
                        if not 
                            break
                        all_data.extend(data)
                        if len(all_data) > FRESH_HISTORY_LIMIT:
                            break

            if not all_
                return False

            all_data.sort(key=lambda x: int(x['issueNumber']))
            self.history.clear()
            for item in all_data[-FRESH_HISTORY_LIMIT:]:
                n = int(item['number'])
                self.history.append({
                    'n': n, 'id': str(item['issueNumber']),
                    's_val': self.get_size_val(n), 'c_val': self.get_color_val(n)
                })

            self.train_engines()
            return True
        except Exception as e:
            print(f"Sync error: {e}")
            return False

    def train_engines(self):
        self.markov_size.clear()
        self.markov_color.clear()

        hist_list = list(self.history)
        for i in range(3, len(hist_list)):
            # Size Markov
            ps = tuple(hist_list[j]['s_val'] for j in range(i-3, i))
            rs = 'BIG' if hist_list[i]['s_val'] == 1 else 'SMALL'
            self.markov_size[ps][rs] += 1

            # Color Markov
            pc = tuple(hist_list[j]['c_val'] for j in range(i-3, i))
            rc = 'GREEN' if hist_list[i]['c_val'] == 1 else 'RED'
            self.markov_color[pc][rc] += 1

    def get_best_bet(self):
        s_pred, s_strength = self.analyze_ensemble('s_val')
        c_pred, c_strength = self.analyze_ensemble('c_val')

        # Kalman bias
        s_final = s_pred * self.kalman_size_prob + (1-s_pred) * (1-self.kalman_size_prob)
        c_final = c_pred * self.kalman_color_prob + (1-c_pred) * (1-self.kalman_color_prob)

        if c_strength * c_final > s_strength * s_final:
            raw_score = c_strength
            final_target = self.get_color_str(c_pred)
            final_type = "COLOR"
        else:
            raw_score = s_strength
            final_target = self.get_size_str(s_pred)
            final_type = "SIZE"

        if raw_score >= 3.0:
            final_level = "SURESHOT"
        elif raw_score >= 2.0:
            final_level = "HIGH"
        elif raw_score >= 1.2:
            final_level = "GOOD"
        else:
            final_level = "LOW"

        return final_target, final_type, final_level, raw_score

    def update_performance(self, raw_score, win):
        score_key = round(raw_score, 1)
        self.score_performance[score_key]['total'] += 1
        if win:
            self.score_performance[score_key]['wins'] += 1

    def reset_session(self):
        self.wins = 0
        self.losses = 0
        self.session_wins = 0
        self.consecutive_losses = 0
        print(">>> SESSION RESET - FRESH DATA PRESERVED <<<")

# ==========================================
# 🔄 V3.1 WORKER - LOSS RECOVERY FIXED
# ==========================================
bot = TitanBrain()
state = {
    "period": "...", "pred": "--", "type": "...", "level": "LOW",
    "wins": 0, "losses": 0, "session": 0, "history": [],
    "bankroll": BANKROLL, "bet_size": 0
}

def worker():
    last_id = None
    while True:
        try:
            if not bot.history:
                bot.sync_data()

            r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=4)
            if r.status_code != 200:
                time.sleep(3)
                continue

            data = r.json()
            if not data.get('data', {}).get('list'):
                time.sleep(3)
                continue

            d = data['data']['list'][0]
            cid = str(d['issueNumber'])
            n = int(d['number'])

            if cid != last_id:
                # Check previous result
                real = None
                status = "WAIT"
                if bot.last_pred and bot.last_pred != "SKIP":
                    win = False
                    if bot.last_type == "SIZE":
                        real = bot.get_size_str(bot.get_size_val(n))
                        win = (bot.last_pred == real)
                        bot.update_kalman('s_val', bot.get_size_val(n))
                    else:
                        real_c = bot.get_color_val(n)
                        real = bot.get_color_str(real_c)
                        win = (bot.last_pred == real)
                        bot.update_kalman('c_val', real_c)

                    bet_amt = state.get('bet_size', 0)
                    if win:
                        bot.bankroll += bet_amt
                        bot.wins += 1
                        bot.session_wins += 1
                        bot.consecutive_losses = 0
                        status = "WIN"
                        bot.update_performance(2.5, True)
                    else:
                        bot.bankroll -= bet_amt
                        bot.losses += 1
                        bot.consecutive_losses += 1
                        status = "LOSS"
                        bot.update_performance(2.5, False)

                # Update UI history
                state["history"].insert(0, {
                    "p": cid[-4:],
                    "r": f"{real} [{bot.last_type[0]}]" if 'real' in locals() else "--",
                    "s": status,
                    "l": bot.last_conf
                })
                state["history"] = state["history"][:20]

                # Session reset
                if bot.session_wins >= 10:
                    bot.reset_session()
                    state["history"] = []
                    state["history"].insert(0, {"p": "RESET", "r": "10WINS!", "s": "DONE", "l": "SUCCESS"})

                # Update fresh data
                bot.history.append({
                    'n': n, 'id': cid,
                    's_val': bot.get_size_val(n),
                    'c_val': bot.get_color_val(n)
                })
                bot.train_engines()

                # V3.1 FIXED THRESHOLD - NO LOSS SPIRAL
                base_thresh = 1.2
                if bot.consecutive_losses >= 4:
                    required_score = base_thresh + 0.3  # 1.5 MAX
                elif bot.session_wins >= 7:
                    required_score = base_thresh - 0.2  # 1.0 FINISH
                else:
                    required_score = base_thresh

                pred, p_type, level, raw_score = bot.get_best_bet()
                bet_size = bot.get_bet_size(level)
                next_period = str(int(cid) + 1)

                # 95% BET RATE
                if raw_score >= required_score and bet_size > 0:
                    bot.last_pred = pred
                    bot.last_type = p_type
                    bot.last_conf = level
                    state.update({
                        "period": next_period, "pred": pred, "type": p_type,
                        "level": level, "wins": bot.wins, "losses": bot.losses,
                        "session": bot.session_wins,
                        "bankroll": round(bot.bankroll, 0),
                        "bet_size": round(bet_size, 0)
                    })
                else:
                    bot.last_pred = "SKIP"
                    bot.last_type = "NONE"
                    bot.last_conf = "LOW"
                    state.update({
                        "period": next_period, "pred": "SKIP", "type": "SKIPPING",
                        "level": "WAIT", "wins": bot.wins, "losses": bot.losses,
                        "session": bot.session_wins,
                        "bankroll": round(bot.bankroll, 0),
                        "bet_size": 0
                    })

                last_id = cid

            time.sleep(1)

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(3)

# Start worker
threading.Thread(target=worker, daemon=True).start()

# ==========================================
# 🌐 PRODUCTION UI
# ==========================================
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>TITAN V3.1 - FRESH 500</title>
    <link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #000; --card: #111; --text: #fff; --green: #00e676; --red: #ff1744; --blue: #2979ff; --yellow: #ffeb3b; --orange: #ff9100; }
        body { background: var(--bg); color: var(--text); font-family: 'Oswald', sans-serif; margin: 0; padding: 15px; text-align: center; text-transform: uppercase; }
        .container { max-width: 500px; margin: 0 auto; }
        .card { background: var(--card); border: 1px solid #222; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .score-row { display: flex; justify-content: space-between; font-size: 20px; margin-bottom: 5px; border-bottom: 1px solid #222; padding-bottom: 10px; }
        .w { color: var(--green); } .l { color: var(--red); }
        .pred-box { margin: 20px 0; min-height: 120px; display: flex; flex-direction: column; justify-content: center; align-items: center; }
        .type-badge { font-size: 14px; color: #666; letter-spacing: 2px; margin-bottom: 5px; }
        .val-BIG { color: var(--blue); font-size: 80px; font-weight: bold; text-shadow: 0 0 20px rgba(41,121,255,0.4); }
        .val-SMALL { color: var(--orange); font-size: 80px; font-weight: bold; text-shadow: 0 0 20px rgba(255,145,0,0.4); }
        .val-GREEN { color: var(--green); font-size: 80px; font-weight: bold; text-shadow: 0 0 20px rgba(0,230,118,0.4); }
        .val-RED { color: var(--red); font-size: 80px; font-weight: bold; text-shadow: 0 0 20px rgba(255,23,68,0.4); }
        .val-SKIP { font-size: 40px; color: #555; animation: pulse 2s infinite; }
        .conf-badge { padding: 5px 15px; border-radius: 4px; font-size: 16px; display: inline-block; color: #000; font-weight: bold; }
        .lvl-WAIT { background: #333; color: #777; }
        .lvl-GOOD { background: var(--blue); }
        .lvl-HIGH { background: var(--green); }
        .lvl-SURESHOT { background: var(--yellow); color: #000; animation: pulse 0.5s infinite; }
        .bankroll { font-size: 18px; color: var(--yellow); }
        .row { display: flex; justify-content: space-between; padding: 12px; background: #0a0a0a; border-radius: 6px; margin-bottom: 5px; align-items: center; border-left: 4px solid #333; }
        .row.WIN { border-left-color: var(--green); }
        .row.LOSS { border-left-color: var(--red); }
        .row.DONE { border-left-color: var(--yellow); }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="score-row">
                <span>TITAN V3.1 FRESH 500</span>
                <span id="bankroll" class="bankroll">₹10,000</span>
            </div>
            <div><span class="w" id="w">W:0</span> <span class="l" id="l">L:0</span></div>
            <div style="font-size:12px;color:#666;">
                PERIOD <span id="p" style="color:#fff;">...</span> | BET ₹<span id="bet">0</span>
            </div>
        </div>
        
        <div class="card">
            <div class="pred-box">
                <div id="type" class="type-badge">SCANNING FRESH DATA...</div>
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
                
                let pEl = document.getElementById('pred');
                let tEl = document.getElementById('type');
                let lEl = document.getElementById('lvl');
                
                if (d.pred === 'SKIP') {
                    tEl.innerText = 'LOW SIGNAL';
                    pEl.innerText = 'SKIPPING';
                    pEl.className = 'val-SKIP';
                    lEl.innerText = 'WAIT';
                    lEl.className = 'conf-badge lvl-WAIT';
                } else {
                    tEl.innerText = `${d.type} FRESH`;
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
            }).catch(e => console.log(e));
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML)

@app.route('/api/status')
def status():
    return jsonify(state)

if __name__ == '__main__':
    if not os.path.exists('trades.csv'):
        with open('trades.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'pred', 'actual', 'level', 'bet', 'pnl', 'bankroll'])
    
    port = int(os.environ.get('PORT', 5003))
    app.run(host='0.0.0.0', port=port, debug=False)

