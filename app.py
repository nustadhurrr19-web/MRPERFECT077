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
HISTORY_LIMIT = 2000

app = Flask(__name__)

# ==========================================
# 🧠 DUAL CORE BRAIN (UPDATED LOGIC)
# ==========================================
class TitanBrain:
    def __init__(self):
        self.history = []
        
        # --- SIZE ENGINE ---
        self.markov_size = defaultdict(lambda: {'BIG': 0, 'SMALL': 0})
        self.pat_size = self.get_patterns()
        
        # --- COLOR ENGINE ---
        self.markov_color = defaultdict(lambda: {'RED': 0, 'GREEN': 0})
        self.pat_color = self.get_patterns() 
        
        # Stats & Session Management
        self.wins = 0
        self.losses = 0
        self.session_wins = 0      # Tracks wins for the 10-win goal
        self.consecutive_losses = 0 # Tracks back-to-back losses
        
        self.last_pred = None     
        self.last_type = "SIZE"   
        self.last_conf = "LOW"
        self.skip_next = False     # Logic to force a skip

    def get_patterns(self):
        # 0 = Small/Red, 1 = Big/Green
        return {
            "11111": 1, "00000": 0, "10101": 0, "01010": 1,
            "11001": 0, "00110": 1, "11100": 0, "00011": 1,
            "10010": 1, "01101": 0, "11011": 0, "00100": 1,
            "11101": 0, "00010": 1, "10001": 0, "01110": 1
        }

    # --- DATA PARSING ---
    def get_size_val(self, n): return 1 if int(n) >= 5 else 0
    def get_size_str(self, s): return "BIG" if s == 1 else "SMALL"
    
    def get_color_val(self, n):
        n = int(n)
        if n in [1, 3, 5, 7, 9]: return 1 # Green
        return 0 # Red

    def get_color_str(self, c): return "GREEN" if c == 1 else "RED"

    def sync_data(self):
        try:
            all_data = []
            try:
                r = requests.get(API_URL, params={"size": str(HISTORY_LIMIT), "pageNo": "1"}, timeout=5)
                if r.status_code == 200:
                    d = r.json().get('data', {}).get('list', [])
                    if len(d) > 100: all_data = d
            except: pass

            if not all_data:
                for p in range(1, 15): 
                    r = requests.get(API_URL, params={"size": "50", "pageNo": str(p)}, timeout=3)
                    if r.status_code == 200:
                        d = r.json().get('data', {}).get('list', [])
                        if not d: break
                        all_data.extend(d)
            
            if not all_data: return False

            all_data.sort(key=lambda x: int(x['issueNumber']))
            
            self.history = []
            for i in all_data:
                n = int(i['number'])
                self.history.append({
                    'n': n,
                    'id': str(i['issueNumber']),
                    's_val': self.get_size_val(n),
                    'c_val': self.get_color_val(n)
                })
            
            if len(self.history) > HISTORY_LIMIT:
                self.history = self.history[-HISTORY_LIMIT:]

            self.train_engines()
            return True
        except: return False

    def train_engines(self):
        self.markov_size.clear()
        self.markov_color.clear()
        
        for i in range(3, len(self.history)):
            ps = (self.history[i-3]['s_val'], self.history[i-2]['s_val'], self.history[i-1]['s_val'])
            rs = 'BIG' if self.history[i]['s_val'] == 1 else 'SMALL'
            self.markov_size[ps][rs] += 1
            
            pc = (self.history[i-3]['c_val'], self.history[i-2]['c_val'], self.history[i-1]['c_val'])
            rc = 'GREEN' if self.history[i]['c_val'] == 1 else 'RED'
            self.markov_color[pc][rc] += 1

    def analyze_core(self, mode):
        pat_res = None
        if len(self.history) >= 6:
            seq = "".join([str(x[mode]) for x in self.history[-5:]])
            pat_res = self.pat_size.get(seq)

        math_res = None
        math_conf = 0.5
        target_markov = self.markov_size if mode == 's_val' else self.markov_color
        t_0 = 'SMALL' if mode == 's_val' else 'RED'
        t_1 = 'BIG' if mode == 's_val' else 'GREEN'
        
        if len(self.history) >= 10:
            last3 = (self.history[-3][mode], self.history[-2][mode], self.history[-1][mode])
            if last3 in target_markov:
                s = target_markov[last3]
                tot = s[t_1] + s[t_0]
                if tot > 0:
                    if s[t_1] > s[t_0]: 
                        math_res = 1
                        math_conf = s[t_1]/tot
                    elif s[t_0] > s[t_1]: 
                        math_res = 0
                        math_conf = s[t_0]/tot
        
        score = 0
        if pat_res is not None: score += 1
        if math_res is not None and math_conf > 0.55: 
            score += 1
            if math_conf > 0.75: score += 1
        
        if pat_res is not None and math_res is not None and pat_res == math_res:
            score += 2
            
        best_pred = pat_res if pat_res is not None else (math_res if math_res is not None else 0)
        
        return best_pred, score, math_conf

    def get_best_bet(self):
        s_pred, s_score, s_conf = self.analyze_core('s_val')
        c_pred, c_score, c_conf = self.analyze_core('c_val')
        
        # Penalty for Color
        c_score_adj = c_score - 1.5
        
        final_target = None
        final_type = "SIZE"
        final_level = "LOW"
        raw_score = 0
        
        if c_score_adj > s_score:
            final_target = self.get_color_str(c_pred)
            final_type = "COLOR"
            raw_score = c_score
        else:
            final_target = self.get_size_str(s_pred)
            final_type = "SIZE"
            raw_score = s_score
            
        if raw_score >= 4: final_level = "SURESHOT"
        elif raw_score >= 3: final_level = "HIGH"
        elif raw_score >= 2: final_level = "GOOD"
        else: final_level = "LOW"
        
        return final_target, final_type, final_level, raw_score

    def reset_session(self):
        self.wins = 0
        self.losses = 0
        self.session_wins = 0
        self.consecutive_losses = 0
        self.history = [] # Optional: clear data or just stats
        # We keep data to maintain prediction accuracy, just reset stats
        print(">>> SESSION RESET: 10 WINS ACHIEVED <<<")

# ==========================================
# 🔄 WORKER (INTELLIGENT SKIP)
# ==========================================
bot = TitanBrain()
state = {
    "period": "...", "pred": "--", "type": "...", "level": "LOW",
    "wins": 0, "losses": 0, "session": 0, "history": []
}

def worker():
    last_id = None
    while True:
        try:
            if not bot.history: bot.sync_data()
            
            r = requests.get(API_URL, params={"size": "1", "pageNo": "1"}, timeout=4)
            d = r.json()['data']['list'][0]
            cid = str(d['issueNumber'])
            n = int(d['number'])
            
            if cid != last_id:
                # 1. CHECK PREVIOUS RESULT
                status = "WAIT"
                if bot.last_pred is not None and bot.last_pred != "SKIP":
                    win = False
                    
                    if bot.last_type == "SIZE":
                        real = bot.get_size_str(bot.get_size_val(n))
                        win = (bot.last_pred == real)
                    else:
                        real_c_val = bot.get_color_val(n)
                        real = bot.get_color_str(real_c_val)
                        win = (bot.last_pred == real)
                    
                    if win:
                        bot.wins += 1
                        bot.session_wins += 1
                        bot.consecutive_losses = 0 # Reset streak
                        status = "WIN"
                    else:
                        bot.losses += 1
                        bot.consecutive_losses += 1
                        status = "LOSS"
                    
                    # Update History UI
                    state["history"].insert(0, {
                        "p": cid[-4:], 
                        "r": f"{real} [{bot.last_type[0]}]", 
                        "s": status, 
                        "l": bot.last_conf
                    })
                    state["history"] = state["history"][:20]

                # 2. SESSION RESET CHECK
                if bot.session_wins >= 10:
                    bot.reset_session()
                    state["history"] = [] # Clear UI history too
                    state["history"].insert(0, {"p": "RESET", "r": "SESSION", "s": "DONE", "l": "10W"})

                # 3. UPDATE DATA
                bot.history.append({
                    'n': n, 'id': cid,
                    's_val': bot.get_size_val(n),
                    'c_val': bot.get_color_val(n)
                })
                bot.train_engines()
                if len(bot.history) > HISTORY_LIMIT: bot.history.pop(0)

                # 4. DETERMINE THRESHOLD
                # Default requires "GOOD" (Score 2) or better. "LOW" (Score < 2) is skipped.
                required_score = 2 
                
                # If 2 losses back to back, Panic/Safe Mode -> Require "HIGH" (Score 3) or "SURESHOT"
                if bot.consecutive_losses >= 2:
                    required_score = 3
                    
                # 5. PREDICT
                pred, p_type, level, raw_score = bot.get_best_bet()
                
                # 6. APPLY SKIP LOGIC
                if raw_score < required_score:
                    # Skip this round
                    bot.last_pred = "SKIP"
                    bot.last_type = "NONE"
                    bot.last_conf = "SKIP"
                    
                    state.update({
                        "period": str(int(cid) + 1),
                        "pred": "SKIP",
                        "type": "SKIPPING",
                        "level": "WAIT", # UI Badge
                        "wins": bot.wins,
                        "losses": bot.losses,
                        "session": bot.session_wins
                    })
                else:
                    # Valid Bet
                    bot.last_pred = pred
                    bot.last_type = p_type
                    bot.last_conf = level
                    
                    state.update({
                        "period": str(int(cid) + 1),
                        "pred": pred,
                        "type": p_type,
                        "level": level,
                        "wins": bot.wins,
                        "losses": bot.losses,
                        "session": bot.session_wins
                    })
                
                last_id = cid
                
            time.sleep(1)
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(5)

threading.Thread(target=worker, daemon=True).start()

# ==========================================
# 🌐 UI (UPDATED FOR SKIP & SESSION)
# ==========================================
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>TITAN V15 PRO</title>
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@400;700&display=swap" rel="stylesheet">
<style>
    :root { 
        --bg: #000; --card: #111; --text: #fff;
        --green: #00e676; --red: #ff1744; --blue: #2979ff; --yellow: #ffeb3b;
    }
    body { background: var(--bg); color: var(--text); font-family: 'Oswald', sans-serif; margin: 0; padding: 15px; text-align: center; text-transform: uppercase; }
    .container { max-width: 500px; margin: 0 auto; }
    
    .card { background: var(--card); border: 1px solid #222; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    
    /* SCORE */
    .score-row { display: flex; justify-content: space-between; font-size: 20px; margin-bottom: 5px; border-bottom: 1px solid #222; padding-bottom: 10px; }
    .session-row { font-size: 14px; color: #888; margin-bottom: 15px; }
    .w { color: var(--green); } .l { color: var(--red); }
    
    /* PREDICTION */
    .pred-box { margin: 20px 0; min-height: 120px; display: flex; flex-direction: column; justify-content: center; align-items: center; }
    .type-badge { font-size: 14px; color: #666; letter-spacing: 2px; margin-bottom: 5px; }
    
    .val-BIG, .val-SMALL { font-size: 80px; font-weight: bold; }
    .val-BIG { color: var(--blue); text-shadow: 0 0 20px rgba(41, 121, 255, 0.4); }
    .val-SMALL { color: #ff9100; text-shadow: 0 0 20px rgba(255, 145, 0, 0.4); }
    
    .val-GREEN { color: var(--green); font-size: 80px; font-weight: bold; text-shadow: 0 0 20px rgba(0, 230, 118, 0.4); }
    .val-RED { color: var(--red); font-size: 80px; font-weight: bold; text-shadow: 0 0 20px rgba(255, 23, 68, 0.4); }
    
    .val-SKIP { font-size: 40px; color: #555; animation: pulse 2s infinite; }
    
    .conf-badge { padding: 5px 15px; border-radius: 4px; font-size: 16px; display: inline-block; color: #000; font-weight: bold; }
    .lvl-WAIT { background: #333; color: #777; }
    .lvl-GOOD { background: var(--blue); }
    .lvl-HIGH { background: var(--green); }
    .lvl-SURESHOT { background: #d500f9; color: #fff; animation: pulse 0.5s infinite; }

    /* HISTORY */
    .row { display: flex; justify-content: space-between; padding: 12px; background: #0a0a0a; border-radius: 6px; margin-bottom: 5px; align-items: center; border-left: 4px solid #333; }
    .row.WIN { border-left-color: var(--green); }
    .row.LOSS { border-left-color: var(--red); }
    .row.DONE { border-left-color: var(--yellow); }
    .res-txt { font-size: 14px; font-weight: bold; }
    
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
</style>
</head>
<body>

<div class="container">
    <div class="card">
        <div class="score-row">
            <span>TITAN V15</span>
            <div><span class="w" id="w">0</span> / <span class="l" id="l">0</span></div>
        </div>
        <div class="session-row">SESSION WINS: <span id="sess" style="color:#fff; font-weight:bold">0</span> / 10</div>
        
        <div style="font-size:12px; color:#666">PERIOD: <span id="p" style="color:#fff">...</span></div>
        
        <div class="pred-box">
            <div id="type" class="type-badge">SCANNING...</div>
            <div id="pred" class="val-BIG">--</div>
            <div style="margin-top:15px"><span id="lvl" class="conf-badge lvl-WAIT">WAIT</span></div>
        </div>
    </div>
    
    <div style="text-align:left; color:#666; font-size:12px; margin-bottom:10px">RECENT RESULTS</div>
    <div id="hist"></div>
</div>

<script>
    setInterval(() => {
        fetch('/api/status').then(r=>r.json()).then(d => {
            document.getElementById('p').innerText = d.period;
            document.getElementById('w').innerText = d.wins;
            document.getElementById('l').innerText = d.losses;
            document.getElementById('sess').innerText = d.session;
            
            let pEl = document.getElementById('pred');
            let tEl = document.getElementById('type');
            let lEl = document.getElementById('lvl');
            
            if (d.pred === "SKIP") {
                tEl.innerText = "WEAK SIGNAL";
                pEl.innerText = "SKIPPING";
                pEl.className = "val-SKIP";
                lEl.innerText = "WAITING FOR SAFE ENTRY";
                lEl.className = "conf-badge lvl-WAIT";
            } else {
                tEl.innerText = d.type + " MARKET";
                pEl.innerText = d.pred;
                pEl.className = `val-${d.pred}`; 
                lEl.innerText = d.level;
                lEl.className = `conf-badge lvl-${d.level}`;
            }
            
            document.getElementById('hist').innerHTML = d.history.map(h => {
                let cls = h.s === "WIN" ? "WIN" : (h.s === "LOSS" ? "LOSS" : "DONE");
                return `<div class="row ${cls}">
                    <span style="color:#666">#${h.p}</span>
                    <span style="color:#eee">${h.r}</span>
                    <span class="res-txt" style="color:${cls=='WIN'?'#00e676':(cls=='LOSS'?'#ff1744':'#ffeb3b')}">${h.s}</span>
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
