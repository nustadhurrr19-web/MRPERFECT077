import requests
import sqlite3
import numpy as np
from datetime import datetime
from collections import Counter

# =====================================================
# 🏛️ CONFIGURATION
# =====================================================
API_URL = "https://api-iok6.onrender.com/api/get_history"
# Using memory ensures speed on Render
DB_FILE = ":memory:" 

# =====================================================
# 🧠 APEX QUANTUM ENGINE (FULLY EXPANDED)
# =====================================================
class ApexQuantum:
    
    def get_size(self, n): 
        # Converts number to size string
        if int(n) >= 5:
            return "BIG"
        else:
            return "SMALL"

    def analyze_bet_type(self, history, current_streak=0):
        """
        Analyzes the history to determine the next prediction.
        
        Args:
            history: List of past results (Newest -> Oldest)
            current_streak: The current loss streak for High/Sureshot bets
            
        Returns:
            best_pred: "BIG" or "SMALL"
            bet_type: "LOW BET", "HIGH BET", "SURESHOT", or "RECOVERY"
            best_strength: A confidence score (0.0 to 1.0)
        """
        
        # We need at least 15 items to find patterns
        if len(history) < 15:
            return "SMALL", "LOW BET", 0.0

        # ---------------------------------------------------------
        # DATA PREPARATION
        # ---------------------------------------------------------
        # Convert history format into a clean list of dictionaries.
        # The input 'history' is ordered Newest -> Oldest.
        formatted_data = []
        for h in history:
            item_dict = {
                's': h['size'], 
                'n': int(h['number'])
            }
            formatted_data.append(item_dict)
        
        # For pattern matching, we need the list to be Oldest -> Newest.
        # This allows us to scan forward in time.
        data_rev = list(reversed(formatted_data))
        
        # ---------------------------------------------------------
        # STEP 1: PATTERN SEARCH (DEPTH 5, 4, 3)
        # ---------------------------------------------------------
        best_pred = None
        best_strength = 0
        
        # We check deep patterns first (length 5), then medium (4), then short (3).
        search_depths = [5, 4, 3]
        
        for depth in search_depths:
            # Get the most recent sequence of 'size' from the end of our data
            # Example: If depth is 3, we take the last 3 results (e.g., BIG, SMALL, BIG)
            last_seq = []
            for x in data_rev[-depth:]:
                last_seq.append(x['s'])
            
            matches = []
            
            # Now scan the entire historical list to find where this sequence occurred before
            # We stop 'depth + 1' from the end so we don't count the current sequence itself
            search_limit = len(data_rev) - (depth + 1)
            
            for i in range(search_limit):
                # Extract a chunk of the same length at position i
                current_chunk = []
                for x in data_rev[i : i+depth]:
                    current_chunk.append(x['s'])
                
                # If the chunk matches our recent sequence...
                if current_chunk == last_seq:
                    # ...record what happened *immediately after* that sequence
                    next_result = data_rev[i+depth]['s']
                    matches.append(next_result)
            
            # If we found matches in history, calculate the probability
            if len(matches) > 0:
                # Count how many BIGs and SMALLs followed this pattern
                counts = Counter(matches)
                # Get the most common result (e.g., 'BIG')
                pred_item = counts.most_common(1)[0][0]
                # Calculate confidence (Times occurred / Total matches)
                strength = counts[pred_item] / len(matches)
                
                best_pred = pred_item
                best_strength = strength
                
                # If we found a pattern, we break the loop (don't search shallower depths)
                break 
        
        # Fallback: If no pattern was found (rare), just use the last result
        if best_pred is None:
            best_pred = data_rev[-1]['s']
            best_strength = 0.5

        # ---------------------------------------------------------
        # STEP 2: APPLY FILTERS (MOMENTUM & SYMMETRY)
        # ---------------------------------------------------------
        
        # Check Momentum: Is the last result the same as our prediction?
        last_val = data_rev[-1]['s']
        is_trending = False
        if last_val == best_pred:
            is_trending = True
        
        # Check Symmetry: Mathematical relationship between last two numbers
        n1 = data_rev[-1]['n'] # Last number
        n2 = data_rev[-2]['n'] # Second to last number
        
        is_symmetric = False
        # Condition A: Do they sum to 9? (e.g., 4 and 5)
        if (n1 + n2) == 9:
            is_symmetric = True
        # Condition B: Are they identical? (e.g., 8 and 8)
        elif n1 == n2:
            is_symmetric = True

        # ---------------------------------------------------------
        # STEP 3: DETERMINE BET TYPE (RECOVERY LOGIC)
        # ---------------------------------------------------------
        bet_type = "LOW BET"
        
        # PRIORITY 1: RECOVERY MODE
        # If the user has lost 2 or more HIGH/SURESHOT bets in a row,
        # we completely override the normal logic to flag this as a RECOVERY bet.
        if current_streak >= 2:
            bet_type = "RECOVERY"
            
        # PRIORITY 2: SURESHOT
        # Requires very high confidence (>85%) AND mathematical symmetry
        elif best_strength > 0.85 and is_symmetric:
            bet_type = "SURESHOT"
            
        # PRIORITY 3: HIGH BET
        # Requires good confidence (>65%) AND matching momentum trend
        elif best_strength > 0.65 and is_trending:
            bet_type = "HIGH BET"
            
        # PRIORITY 4: LOW BET
        # Everything else falls into this category
        else:
            bet_type = "LOW BET"
            
        return best_pred, bet_type, best_strength

# =====================================================
# ⚙️ STORAGE (DATABASE MANAGER)
# =====================================================
class OmegaStorage:
    def __init__(self):
        # Connect to an in-memory SQLite database
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Create the table if it doesn't exist
        create_table_sql = '''
            CREATE TABLE IF NOT EXISTS results (
                issue TEXT PRIMARY KEY, 
                number INTEGER, 
                size TEXT, 
                color TEXT, 
                timestamp TEXT
            )
        '''
        self.cursor.execute(create_table_sql)
        self.conn.commit()
    
    def sync_fast(self):
        """
        Fetches 100 records (5 pages) from the API to initialize the database.
        This matches the logic used in NEW4.PY but ensures web compatibility.
        """
        all_data = []
        
        # Loop through pages 1 to 5
        for page in range(1, 6): 
            try:
                # Request data from API
                params = {
                    "size": "20", 
                    "pageSize": "20", 
                    "pageNo": str(page)
                }
                r = requests.get(API_URL, params=params, timeout=2)
                
                if r.status_code == 200:
                    json_data = r.json()
                    data_list = json_data.get('data', {}).get('list', [])
                    
                    if not data_list:
                        break
                        
                    all_data.extend(data_list)
                else:
                    break
            except: 
                break
            
        # Process and insert data into database
        bulk_data = []
        for item in all_data:
            try:
                issue = str(item['issueNumber'])
                num = int(item['number'])
                
                # Determine Size
                if num >= 5:
                    s = "BIG"
                else:
                    s = "SMALL"
                
                # Determine Color (Standard Wingo Rules)
                if num in [0, 5]:
                    c = "VIOLET"
                elif num % 2 == 1:
                    c = "GREEN"
                else:
                    c = "RED"
                
                current_time = str(datetime.now())
                
                record = (issue, num, s, c, current_time)
                bulk_data.append(record)
            except: 
                continue
            
        if len(bulk_data) > 0:
            insert_sql = "INSERT OR IGNORE INTO results VALUES (?, ?, ?, ?, ?)"
            self.cursor.executemany(insert_sql, bulk_data)
            self.conn.commit()

    def get_history(self, limit=2000):
        """
        Retrieves the latest history from the database.
        """
        try:
            select_sql = f"SELECT issue, number, size, color FROM results ORDER BY issue DESC LIMIT {limit}"
            self.cursor.execute(select_sql)
            rows = self.cursor.fetchall()
            
            result_list = []
            for r in rows:
                item = {
                    "issue": r[0], 
                    "number": r[1], 
                    "size": r[2], 
                    "color": r[3]
                }
                result_list.append(item)
                
            return result_list
        except: 
            return []