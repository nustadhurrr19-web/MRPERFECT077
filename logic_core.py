import requests
import sqlite3
import numpy as np
from datetime import datetime
from collections import Counter

# =====================================================
# 🏛️ CORE CONFIGURATION
# =====================================================
API_URL = "https://api-iok6.onrender.com/api/get_history"
DB_FILE = ":memory:"

# =====================================================
# 🧠 APEX QUANTUM ENGINE (V2 ULTIMATE)
# =====================================================
class ApexQuantum:
    
    def get_size(self, n): 
        return "BIG" if int(n) >= 5 else "SMALL"

    def get_pattern_strength(self, history, depth):
        """Helper to check a specific depth pattern."""
        if len(history) < depth + 1: return None, 0
        
        # history is Newest -> Oldest. We need Oldest -> Newest for scanning.
        data_rev = list(reversed([{'s': h['size']} for h in history]))
        
        last_seq = [x['s'] for x in data_rev[-depth:]]
        matches = []
        
        search_limit = len(data_rev) - (depth + 1)
        for i in range(search_limit):
            current_chunk = [x['s'] for x in data_rev[i : i+depth]]
            if current_chunk == last_seq:
                matches.append(data_rev[i+depth]['s'])
        
        if matches:
            counts = Counter(matches)
            pred_item = counts.most_common(1)[0][0]
            strength = counts[pred_item] / len(matches)
            return pred_item, strength
        return None, 0

    def analyze_bet_type(self, history, current_streak=0):
        """
        Apex V2 Logic: Conflict Filters, ZigZag, and Smart Recovery.
        Returns: Prediction (or None), Bet Type, Strength
        """
        if len(history) < 15: return None, "WAITING...", 0.0

        # 1. MULTI-DEPTH ANALYSIS (The Conflict Filter)
        # We check Long-term (5) vs Short-term (3)
        pred5, str5 = self.get_pattern_strength(history, 5)
        pred3, str3 = self.get_pattern_strength(history, 3)
        pred4, str4 = self.get_pattern_strength(history, 4)

        best_pred = None
        best_strength = 0

        # CONFLICT CHECK: If Depth 5 says BIG and Depth 3 says SMALL -> SKIP
        if pred5 and pred3 and pred5 != pred3:
            # Only override conflict if one is a "Super Sureshot" (>90%)
            if str5 > 0.90: 
                best_pred, best_strength = pred5, str5
            elif str3 > 0.90: 
                best_pred, best_strength = pred3, str3
            else:
                return None, "WAITING... (CONFLICT)", 0.0
        else:
            best_pred = pred5 if str5 >= str4 else pred4
            best_strength = max(str5, str4, str3)

        if not best_pred:
            best_pred = history[0]['size'] # Default to last result
            best_strength = 0.5

        # 2. DYNAMIC THRESHOLDS (Panic Adjustment)
        sureshot_req = 0.85
        high_req = 0.65
        
        if current_streak > 0:
            sureshot_req += 0.05
            high_req += 0.05

        # 3. PATTERN FILTERS
        last_val = history[0]['size']
        prev_val = history[1]['size']
        
        is_trending = (last_val == best_pred)
        is_zigzag = (last_val != prev_val and best_pred != last_val)

        # Symmetry Check
        n1 = int(history[0]['number'])
        n2 = int(history[1]['number'])
        is_symmetric = (n1 + n2 == 9) or (n1 == n2)

        # 4. FINAL DECISION TREE
        if current_streak >= 2:
            if best_strength < 0.50: 
                return None, "SKIP (VOLATILE)", 0.0
            return best_pred, "RECOVERY", best_strength

        elif best_strength > sureshot_req and is_symmetric:
            return best_pred, "SURESHOT", best_strength
            
        elif best_strength > high_req and (is_trending or is_zigzag):
            return best_pred, "HIGH BET", best_strength
            
        else:
            return None, "WAITING...", 0.0

# =====================================================
# 🗄️ OMEGA STORAGE (FAST BOOT VERSION)
# =====================================================
class OmegaStorage:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS results (issue TEXT PRIMARY KEY, number INTEGER, size TEXT, color TEXT, timestamp TEXT)''')
        self.conn.commit()
    
    def sync_fast(self):
        """
        Fetches latest 500 results page-by-page.
        UPDATED: Commits data immediately so UI loads instantly.
        """
        # LOOP 25 TIMES x 20 ITEMS = 500 RECORDS
        for page in range(1, 26): 
            try:
                # Fetch 1 page
                r = requests.get(API_URL, params={"size": "20", "pageSize": "20", "pageNo": str(page)}, timeout=2)
                
                if r.status_code == 200:
                    data = r.json().get('data', {}).get('list', [])
                    if not data: break
                    
                    # PROCESS & INSERT IMMEDIATELY (Don't wait for all pages)
                    bulk_data = []
                    for item in data:
                        try:
                            issue = str(item['issueNumber'])
                            num = int(item['number'])
                            s = "BIG" if num >= 5 else "SMALL"
                            
                            if num in [0, 5]: c = "VIOLET"
                            elif num % 2 == 1: c = "GREEN"
                            else: c = "RED"
                            
                            bulk_data.append((issue, num, s, c, str(datetime.now())))
                        except: continue
                    
                    if bulk_data:
                        self.cursor.executemany("INSERT OR IGNORE INTO results VALUES (?, ?, ?, ?, ?)", bulk_data)
                        self.conn.commit() # <--- THIS MAKES IT SHOW INSTANTLY
                        
                else: 
                    break
            except: 
                break
            
    def get_history(self, limit=2000):
        try:
            self.cursor.execute(f"SELECT issue, number, size, color FROM results ORDER BY issue DESC LIMIT {limit}")
            return [{"issue": r[0], "number": r[1], "size": r[2], "color": r[3]} for r in self.cursor.fetchall()]
        except: return []
