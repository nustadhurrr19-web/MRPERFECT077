#!/usr/bin/env python3

import requests
import time
import threading
from collections import defaultdict, Counter
from sklearn.ensemble import GradientBoostingClassifier
from flask import Flask, render_template_string, jsonify

# =====================================================
# CONFIG
# =====================================================

API_URL = "https://wingo1min.onrender.com/api/get_history"
HISTORY_LIMIT = 2000
TRAIN_SIZE = 500
BASE_CONF = 0.52   # BALANCED

# =====================================================
# GLOBAL STATE FOR UI
# =====================================================

APP_STATE = {
    "current_period": "WAITING",
    "current_prediction": "ANALYZING...",
    "wins": 0,
    "losses": 0,
    "current_win_streak": 0,
    "current_loss_streak": 0,
    "max_win_streak": 0,
    "max_loss_streak": 0,
    "status": "INITIALIZING AI...",
    "history": []
}

def reset_stats():
    APP_STATE["wins"] = 0
    APP_STATE["losses"] = 0
    APP_STATE["current_win_streak"] = 0
    APP_STATE["current_loss_streak"] = 0
    APP_STATE["max_win_streak"] = 0
    APP_STATE["max_loss_streak"] = 0
    APP_STATE["history"] = []
    APP_STATE["status"] = "STATS RESET AFTER 20 WINS"

# =====================================================
# DATA MANAGER
# =====================================================

class DataManager:

    def __init__(self):
        self.history = []

    def size(self, n):
        return "BIG" if int(n) >= 5 else "SMALL"

    def sync(self):

        raw = []

        for p in range(1, 20):
            try:
                r = requests.get(
                    API_URL,
                    params={"size": "50", "pageNo": str(p)},
                    timeout=6
                )
                data = r.json()["data"]["list"]
                if not data:
                    break
                raw.extend(data)
            except:
                continue

        raw.sort(key=lambda x: int(x["issueNumber"]))

        self.history = [{
            "id": str(i["issueNumber"]),
            "n": int(i["number"]),
            "res": self.size(i["number"])
        } for i in raw][-HISTORY_LIMIT:]

        return len(self.history) > 100

# =====================================================
# AI CORE
# =====================================================

class AiCore:

    def __init__(self):

        self.model = GradientBoostingClassifier(
            n_estimators=120,
            learning_rate=0.05,
            max_depth=4
        )

        self.trained = False

    def extract(self, h, index):

        f = []

        for j in range(1, 7):
            if index-j >= 0:
                f.append(1 if h[index-j]["res"] == "BIG" else 0)
            else:
                f.append(0)

        streak = 0
        if index > 0:
            c = h[index-1]["res"]
            for k in range(1, 10):
                if index-k >= 0 and h[index-k]["res"] == c:
                    streak += 1
                else:
                    break

        f.append(streak)
        f.append(h[index-1]["n"] % 3 if index > 0 else 0)

        return f

    def train(self, h):

        X = []
        y = []

        start = max(10, len(h) - TRAIN_SIZE)

        for i in range(start, len(h)):
            X.append(self.extract(h, i))
            y.append(1 if h[i]["res"] == "BIG" else 0)

        if len(set(y)) > 1:
            self.model.fit(X, y)
            self.trained = True

    def predict(self, h):

        if not self.trained:
            return "WAIT", 0

        feat = self.extract(h, len(h))
        probs = self.model.predict_proba([feat])[0]

        if probs[1] > probs[0]:
            return "BIG", probs[1]
        else:
            return "SMALL", probs[0]

# =====================================================
# MARKOV CORE
# =====================================================

class MarkovCore:

    def __init__(self):
        self.chain = defaultdict(lambda: {"BIG": 0, "SMALL": 0})

    def train(self, h):

        self.chain.clear()

        for i in range(3, len(h)):
            k = (h[i-3]["res"], h[i-2]["res"], h[i-1]["res"])
            self.chain[k][h[i]["res"]] += 1

    def predict(self, h):

        if len(h) < 3:
            return "WAIT", 0

        k = (h[-3]["res"], h[-2]["res"], h[-1]["res"])

        stats = self.chain.get(k, {"BIG": 0, "SMALL": 0})
        total = stats["BIG"] + stats["SMALL"]

        if total < 4:
            return "WAIT", 0

        p = stats["BIG"] / total

        if p > 0.5:
            return "BIG", p
        elif p < 0.5:
            return "SMALL", 1-p

        return "WAIT", 0

# =====================================================
# DEEP PATTERN
# =====================================================

class DeepPattern:

    def predict(self, h):

        if len(h) < 20:
            return "WAIT", 0

        s = "".join("B" if x["res"] == "BIG" else "S" for x in h)

        best = "WAIT"
        best_conf = 0

        for depth in range(6, 2, -1):

            cur = s[-depth:]
            matches = []

            for i in range(len(s)-depth):
                if s[i:i+depth] == cur and i+depth < len(s):
                    matches.append(s[i+depth])

            if len(matches) >= 3:
                c = Counter(matches)
                top = c.most_common(1)[0]
                conf = top[1] / len(matches)

                if conf > best_conf:
                    best_conf = conf
                    best = "BIG" if top[0] == "B" else "SMALL"

        return best, best_conf

# =====================================================
# ANOMALY DETECTOR
# =====================================================

class AnomalyDetector:

    def check(self, h):

        if len(h) < 20:
            return False

        nums = [x["n"] for x in h[-20:]]

        for i in range(len(nums)-2):
            if nums[i] == nums[i+1] == nums[i+2]:
                return True

        c = Counter(nums)

        if c.most_common(1)[0][1] > 6:
            return True

        return False

# =====================================================
# JARVIS BALANCED
# =====================================================

class Jarvis:

    def __init__(self):

        self.loss_streak = 0
        self.ai_weight = 1.4

    def resolve(self, win):

        if win:
            self.loss_streak = max(0, self.loss_streak-1)
            self.ai_weight *= 1.01
        else:
            self.loss_streak += 1
            self.ai_weight *= 0.99

        self.ai_weight = max(0.9, min(1.8, self.ai_weight))

    def required_conf(self):

        if self.loss_streak == 0:
            return BASE_CONF
        elif self.loss_streak == 1:
            return BASE_CONF + 0.04
        else:
            return BASE_CONF + 0.08

# =====================================================
# PERFECT X AI (MODIFIED FOR FLASK STATE)
# =====================================================

class PerfectXAI:

    def __init__(self):

        self.dm = DataManager()
        self.ai = AiCore()
        self.mk = MarkovCore()
        self.dp = DeepPattern()
        self.anomaly = AnomalyDetector()
        self.jarvis = Jarvis()

        self.last_id = None
        self.active_pred = None
        self.active_issue = None

    def start(self):

        APP_STATE["status"] = "SYNCING DATA..."
        print("PERFECT X AI BALANCED MODE STARTING...")

        if not self.dm.sync():
            APP_STATE["status"] = "SYNC FAILED"
            print("SYNC FAILED")
            return

        APP_STATE["status"] = "TRAINING MODELS..."
        self.ai.train(self.dm.history)
        self.mk.train(self.dm.history)

        self.last_id = self.dm.history[-1]["id"]
        
        APP_STATE["status"] = "RUNNING AND ANALYZING"
        print("RUNNING...\n")

        while True:

            try:

                r = requests.get(API_URL,
                                 params={"size":"1","pageNo":"1"},
                                 timeout=5)

                d = r.json()["data"]["list"][0]

                cid = str(d["issueNumber"])
                num = int(d["number"])
                res = "BIG" if num >= 5 else "SMALL"

                if cid != self.last_id:

                    # Resolve previous prediction
                    if self.active_pred and self.active_pred != "SKIP":

                        if self.active_pred == res:
                            print(f"NEXT : {self.active_issue[-4:]} PREDICT ⏩ : {self.active_pred} ⏳WIN✅✅")
                            self.jarvis.resolve(True)
                            
                            APP_STATE["wins"] += 1
                            APP_STATE["current_win_streak"] += 1
                            APP_STATE["current_loss_streak"] = 0
                            APP_STATE["max_win_streak"] = max(APP_STATE["max_win_streak"], APP_STATE["current_win_streak"])
                            
                            APP_STATE["history"].insert(0, {
                                "period": self.active_issue[-4:],
                                "pred": self.active_pred,
                                "res": "WIN"
                            })
                            
                            # 20 WINS RESET LOGIC
                            if APP_STATE["wins"] >= 20:
                                reset_stats()

                        else:
                            print(f"NEXT : {self.active_issue[-4:]} PREDICT ⏩ : {self.active_pred} ⏳LOS❌❌")
                            self.jarvis.resolve(False)
                            
                            APP_STATE["losses"] += 1
                            APP_STATE["current_loss_streak"] += 1
                            APP_STATE["current_win_streak"] = 0
                            APP_STATE["max_loss_streak"] = max(APP_STATE["max_loss_streak"], APP_STATE["current_loss_streak"])
                            
                            APP_STATE["history"].insert(0, {
                                "period": self.active_issue[-4:],
                                "pred": self.active_pred,
                                "res": "LOSS"
                            })
                            
                    # Keep history concise
                    if len(APP_STATE["history"]) > 50:
                        APP_STATE["history"] = APP_STATE["history"][:50]

                    # Update DataManager History
                    self.dm.history.append({
                        "id": cid,
                        "n": num,
                        "res": res
                    })

                    if len(self.dm.history) > HISTORY_LIMIT:
                        self.dm.history.pop(0)

                    if int(cid) % 5 == 0:
                        self.ai.train(self.dm.history)
                        self.mk.train(self.dm.history)

                    next_id = str(int(cid)+1)
                    APP_STATE["current_period"] = next_id[-4:]

                    if self.anomaly.check(self.dm.history):
                        self.active_pred = "SKIP"
                        self.active_issue = next_id
                        APP_STATE["current_prediction"] = "ANALYZING..."
                        print(f"NEXT : {next_id[-4:]} PREDICT ⏩ : SKIP ⏳WATINGG")
                        self.last_id=cid
                        continue

                    ai_p, ai_c = self.ai.predict(self.dm.history)
                    mk_p, mk_c = self.mk.predict(self.dm.history)
                    dp_p, dp_c = self.dp.predict(self.dm.history)

                    votes = {"BIG":0,"SMALL":0}
                    w = 0

                    if ai_p!="WAIT":
                        votes[ai_p]+=ai_c*self.jarvis.ai_weight
                        w += self.jarvis.ai_weight

                    if mk_p!="WAIT":
                        votes[mk_p]+=mk_c
                        w += 1

                    if dp_p!="WAIT":
                        votes[dp_p]+=dp_c
                        w += 1

                    if w == 0:
                        final="SKIP"
                        conf=0
                    else:
                        final="BIG" if votes["BIG"]>votes["SMALL"] else "SMALL"
                        conf=votes[final]/w

                    req=self.jarvis.required_conf()

                    if final!="SKIP" and conf>=req:
                        self.active_pred = final
                        self.active_issue = next_id
                        APP_STATE["current_prediction"] = final
                        print(f"NEXT : {next_id[-4:]} PREDICT ⏩ : {final} ⏳WATINGG")
                    else:
                        self.active_pred = "SKIP"
                        self.active_issue = next_id
                        APP_STATE["current_prediction"] = "ANALYZING..."
                        print(f"NEXT : {next_id[-4:]} PREDICT ⏩ : SKIP ⏳WATINGG")

                    self.last_id=cid

                time.sleep(1)

            except KeyboardInterrupt:
                print("STOPPED")
                break
            except Exception as e:
                time.sleep(2)


# =====================================================
# FLASK WEB SERVER & UI
# =====================================================

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Perfect X AI - Dashboard</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --win-color: #22c55e;
            --loss-color: #ef4444;
            --big-color: #f59e0b;
            --small-color: #8b5cf6;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        body { background-color: var(--bg-color); color: var(--text-main); padding: 20px; }
        
        .container { max-width: 1000px; margin: 0 auto; }
        header { text-align: center; margin-bottom: 30px; }
        header h1 { color: var(--accent); font-size: 2.5rem; text-transform: uppercase; letter-spacing: 2px; }
        header p { color: var(--text-muted); font-size: 1rem; }
        
        .main-prediction { background: var(--card-bg); border-radius: 16px; padding: 30px; text-align: center; margin-bottom: 30px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5); border: 1px solid #334155; }
        .main-prediction .period { font-size: 1.2rem; color: var(--text-muted); margin-bottom: 10px; }
        .main-prediction .pred-value { font-size: 4rem; font-weight: bold; margin: 10px 0; }
        .pred-BIG { color: var(--big-color); }
        .pred-SMALL { color: var(--small-color); }
        .pred-ANALYZING { color: var(--text-muted); font-size: 2.5rem !important; }
        
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .stat-card { background: var(--card-bg); padding: 20px; border-radius: 12px; text-align: center; border: 1px solid #334155; }
        .stat-card h3 { font-size: 0.9rem; color: var(--text-muted); margin-bottom: 10px; text-transform: uppercase; }
        .stat-card .value { font-size: 1.8rem; font-weight: bold; }
        .val-win { color: var(--win-color); }
        .val-loss { color: var(--loss-color); }
        
        .history-section { background: var(--card-bg); border-radius: 16px; padding: 20px; border: 1px solid #334155; }
        .history-section h2 { margin-bottom: 20px; font-size: 1.2rem; color: var(--accent); border-bottom: 1px solid #334155; padding-bottom: 10px; }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #334155; }
        th { color: var(--text-muted); font-size: 0.9rem; text-transform: uppercase; }
        .res-WIN { color: var(--win-color); font-weight: bold; }
        .res-LOSS { color: var(--loss-color); font-weight: bold; }
        
        @media (max-width: 600px) {
            header h1 { font-size: 2rem; }
            .main-prediction .pred-value { font-size: 3rem; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Perfect X AI</h1>
            <p id="system-status">INITIALIZING...</p>
        </header>

        <div class="main-prediction">
            <div class="period">Next Period: <strong id="ui-period">----</strong></div>
            <div id="ui-prediction" class="pred-value pred-ANALYZING">ANALYZING...</div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Wins</h3>
                <div class="value val-win" id="ui-wins">0</div>
            </div>
            <div class="stat-card">
                <h3>Total Loss</h3>
                <div class="value val-loss" id="ui-losses">0</div>
            </div>
            <div class="stat-card">
                <h3>Cur. Win Streak</h3>
                <div class="value" id="ui-c-win">0</div>
            </div>
            <div class="stat-card">
                <h3>Cur. Loss Streak</h3>
                <div class="value" id="ui-c-loss">0</div>
            </div>
            <div class="stat-card">
                <h3>Max Win Streak</h3>
                <div class="value val-win" id="ui-m-win">0</div>
            </div>
            <div class="stat-card">
                <h3>Max Loss Streak</h3>
                <div class="value val-loss" id="ui-m-loss">0</div>
            </div>
        </div>

        <div class="history-section">
            <h2>Recent Predictions (No Skips)</h2>
            <table>
                <thead>
                    <tr>
                        <th>Period</th>
                        <th>Prediction</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody id="ui-history">
                    </tbody>
            </table>
        </div>
    </div>

    <script>
        function updateUI() {
            fetch('/api/state')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('system-status').innerText = data.status;
                    document.getElementById('ui-period').innerText = data.current_period;
                    
                    const predEl = document.getElementById('ui-prediction');
                    predEl.innerText = data.current_prediction;
                    predEl.className = 'pred-value'; 
                    if(data.current_prediction === 'BIG') predEl.classList.add('pred-BIG');
                    else if(data.current_prediction === 'SMALL') predEl.classList.add('pred-SMALL');
                    else predEl.classList.add('pred-ANALYZING');

                    document.getElementById('ui-wins').innerText = data.wins;
                    document.getElementById('ui-losses').innerText = data.losses;
                    document.getElementById('ui-c-win').innerText = data.current_win_streak;
                    document.getElementById('ui-c-loss').innerText = data.current_loss_streak;
                    document.getElementById('ui-m-win').innerText = data.max_win_streak;
                    document.getElementById('ui-m-loss').innerText = data.max_loss_streak;

                    const tbody = document.getElementById('ui-history');
                    tbody.innerHTML = '';
                    data.history.forEach(item => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td>${item.period}</td>
                            <td>${item.pred}</td>
                            <td class="res-${item.res}">${item.res}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                })
                .catch(err => console.error("Error fetching state:", err));
        }

        setInterval(updateUI, 1000);
        updateUI();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/state")
def get_state():
    return jsonify(APP_STATE)


# =====================================================
# START
# =====================================================

if __name__=="__main__":
    # Start AI core in background thread
    ai_bot = PerfectXAI()
    ai_thread = threading.Thread(target=ai_bot.start)
    ai_thread.daemon = True 
    ai_thread.start()
    
    # Start Flask Web Server
    print("===================================================")
    print(" WEB DASHBOARD RUNNING AT: http://localhost:5000")
    print("===================================================")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
