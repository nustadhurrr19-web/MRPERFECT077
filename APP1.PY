import os
from datetime import datetime
from flask import Flask, render_template_string, request, session, redirect, url_for
from logic_core import ApexQuantum, OmegaStorage

# =====================================================
# 🏛️ CONFIGURATION
# =====================================================
app = Flask(__name__)
# Generate a random secret key for session security
app.secret_key = os.urandom(24)

# 🔐 SECURITY SETTINGS
ACCESS_KEY = "perfect007"
# Expiration set to Feb 6, 2026
EXPIRY_DATE = datetime(2026, 2, 6, 23, 59) 

# Initialize Logic Class and Database Class
db = OmegaStorage()
brain = ApexQuantum()

# =====================================================
# 🌐 UI TEMPLATES
# =====================================================

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>APEX LOGIN</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { background: #000; color: #00ff00; font-family: 'Consolas', 'Monaco', monospace; display: flex; height: 100vh; align-items: center; justify-content: center; margin: 0; }
        .box { border: 2px solid #00ff00; padding: 20px; width: 300px; text-align: center; }
        input { background: #000; color: #fff; border: 1px solid #333; padding: 10px; width: 80%; font-family: monospace; text-align: center; margin: 10px 0; }
        button { background: #00ff00; color: #000; border: none; padding: 10px 20px; font-weight: bold; cursor: pointer; width: 100%; font-family: monospace; }
        .err { color: red; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="box">
        <h3>[ APEX QUANTUM ]</h3>
        <form method="POST">
            <input type="password" name="key" placeholder="ENTER KEY" required>
            <button type="submit">LOGIN >> </button>
        </form>
        {% if error %}<div class="err">{{ error }}</div>{% endif %}
    </div>
</body>
</html>
"""

TERMINAL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>APEX QUANTUM UI</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="30">
    <style>
        body { background-color: #000000; color: #e0e0e0; font-family: 'Consolas', 'Monaco', monospace; margin: 0; padding: 15px; font-size: 14px; }
        a { text-decoration: none; }
        
        .header { border-bottom: 1px dashed #333; padding-bottom: 10px; margin-bottom: 20px; color: #666; }
        .btn-refresh { display: block; background: #111; color: #00ff00; text-align: center; padding: 10px; margin-bottom: 20px; border: 1px solid #333; font-weight: bold; text-transform: uppercase; }
        .block { margin-bottom: 25px; }
        
        .tag-high { background-color: #d4ac0d; color: #000; padding: 2px 8px; font-weight: bold; display: inline-block; }
        .tag-low { background-color: #0044cc; color: #fff; padding: 2px 8px; font-weight: bold; display: inline-block; }
        .tag-sureshot { background-color: #ff0000; color: #fff; padding: 2px 8px; font-weight: bold; display: inline-block; border: 1px solid yellow; }
        .tag-recovery { background-color: #00aa00; color: #fff; padding: 2px 8px; font-weight: bold; display: inline-block; border: 1px solid white; box-shadow: 0 0 10px green; }
        
        .period-text { color: #888; margin-left: 5px; }
        .target-line { margin-top: 4px; font-size: 16px; }
        
        .res-line { margin-top: 5px; font-size: 14px; }
        .win-icon { color: #00ff00; font-weight: bold; }
        .loss-icon { color: #ff0055; font-weight: bold; }
        .wait-icon { color: #666; }
        .loss-streak { color: #888; font-size: 12px; margin-left: 5px; }
    </style>
</head>
<body>
    <div class="header">
        > ENGINE: APEX_QUANTUM<br>
        > DB_RECORDS: {{ db_count }}<br>
        > USER: TEJAS BHAVSAR
    </div>

    <a href="/" class="btn-refresh">[ SYNC DATA ]</a>

    <div class="block">
        <div>
            {% if tag_type == 'RECOVERY' %}
                <span class="tag-recovery">🚨 RECOVERY</span>
            {% elif tag_type == 'SURESHOT' %}
                <span class="tag-sureshot">💎 SURESHOT</span>
            {% elif tag_type == 'HIGH BET' %}
                <span class="tag-high">🔥 HIGH BET</span>
            {% else %}
                <span class="tag-low">🔹 LOW BET</span>
            {% endif %}
            <span class="period-text">| Period: {{ next_issue }}</span>
        </div>
        <div class="target-line">
            Target: <span style="color: {{ 'yellow' if pred == 'BIG' else '#00aaff' }}; font-weight: bold;">{{ pred }}</span>
        </div>
    </div>

    <div style="border-bottom: 1px dashed #333; margin: 20px 0;"></div>

    {% for row in history_rows %}
    <div class="block">
        <div>
            {% if row.tag == 'RECOVERY' %}
                <span class="tag-recovery">🚨 RECOVERY</span>
            {% elif row.tag == 'SURESHOT' %}
                <span class="tag-sureshot">💎 SURESHOT</span>
            {% elif row.tag == 'HIGH BET' %}
                <span class="tag-high">🔥 HIGH BET</span>
            {% else %}
                <span class="tag-low">🔹 LOW BET</span>
            {% endif %}
            <span class="period-text">| Period: {{ row.issue }} | Target: {{ row.pred }}</span>
        </div>
        
        <div class="res-line">
            {% if row.res == 'WIN' %}
                <span class="win-icon">✅ WIN</span>
            {% elif row.res == 'LOSS' %}
                <span class="loss-icon">❌ LOSS</span>
            {% else %}
                <span class="wait-icon">⏳ WAIT</span>
            {% endif %}
            
            <span style="color:#ccc"> | Result: {{ row.actual }}</span>
            
            {% if row.streak > 0 %}
                <span class="loss-streak">(Loss Streak: {{ row.streak }})</span>
            {% endif %}
        </div>
    </div>
    {% endfor %}

</body>
</html>
"""

# =====================================================
# 🛤️ ROUTES
# =====================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login with key validation."""
    error = None
    if request.method == 'POST':
        user_key = request.form.get('key')
        
        if user_key == ACCESS_KEY:
            # Check if key is expired
            if datetime.now() > EXPIRY_DATE:
                error = "KEY EXPIRED"
            else:
                session['logged_in'] = True
                return redirect(url_for('dashboard'))
        else:
            error = "INVALID KEY"
            
    return render_template_string(LOGIN_HTML, error=error)

@app.route('/')
def dashboard():
    """Main dashboard logic with Streak Replay Engine."""
    if not session.get('logged_in'): 
        return redirect(url_for('login'))
    
    # 1. FETCH DATA
    db.sync_fast() 
    
    history = db.get_history(2000)
    if not history: 
        return "LOADING DATA... PLEASE REFRESH IN 5 SECONDS"

    # 3. REPLAY ENGINE: CALCULATE HISTORICAL STREAKS
    # We must scan history from Oldest -> Newest to correctly calculate
    # what the 'streak' was at any given moment in the past.
    
    # We analyze the last 50 rounds to ensure accuracy
    analysis_slice = history[:50] 
    
    # Reverse so we iterate from Oldest -> Newest
    analysis_slice.reverse() 
    
    processed_rows = []
    current_high_loss_streak = 0
    
    # Loop through past rounds to build up the streak state
    # We stop at len-1 because the last item is our 'Next Prediction' context
    for i in range(len(analysis_slice) - 1): 
        current_item = analysis_slice[i+1] # The result we are checking
        past_context = analysis_slice[:i+1] # All data available BEFORE that result
        
        # The Brain expects history in Newest -> Oldest format
        brain_context = list(reversed(past_context))
        
        # Skip if not enough data
        if len(brain_context) < 15: 
            continue 
        
        # PREDICT using the streak known AT THAT TIME
        p_pred, p_tag, p_conf = brain.analyze_bet_type(brain_context, current_high_loss_streak)
        
        actual = current_item['size']
        res = "LOSS"
        if p_pred == actual: 
            res = "WIN"
        
        # SAVE STATE FOR DISPLAY
        # We want to show what the streak was *entering* this round
        streak_for_display = current_high_loss_streak

        # UPDATE STREAK FOR NEXT ROUND (The Replay Logic)
        if res == "WIN":
            # Any Win resets the High Loss Streak
            current_high_loss_streak = 0
        elif res == "LOSS":
            # Only High Priority Bets increase the streak
            if p_tag in ["HIGH BET", "SURESHOT", "RECOVERY"]:
                current_high_loss_streak += 1
            # Low Bets are ignored (streak stays the same)

        processed_rows.append({
            "issue": current_item['issue'],
            "pred": p_pred,
            "conf": int(p_conf*100),
            "tag": p_tag,
            "res": res,
            "actual": actual,
            "streak": streak_for_display 
        })

    # 4. PREDICT THE FUTURE (NEXT ROUND)
    # Now that we have the accurate 'current_high_loss_streak', we predict the next live round
    pred, tag_type, conf = brain.analyze_bet_type(history, current_high_loss_streak)
    
    # Calculate Next Issue Number
    try: 
        next_issue = int(history[0]['issue']) + 1
    except: 
        next_issue = "Unknown"

    # 5. PREPARE FINAL DISPLAY
    # Reverse back to Newest -> Oldest for the HTML list
    processed_rows.reverse()
    
    # Slice the top 10 for the UI
    display_rows = processed_rows[:10] 

    return render_template_string(TERMINAL_HTML, 
                                  next_issue=next_issue, 
                                  pred=pred, 
                                  conf=int(conf*100), 
                                  tag_type=tag_type,
                                  db_count=len(history),
                                  history_rows=display_rows)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10001))
    app.run(host='0.0.0.0', port=port)