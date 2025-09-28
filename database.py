import sqlite3
from datetime import datetime, timedelta

DATABASE_FILE = 'tracker.db'

def get_db_connection():
    """Creates and returns a database connection."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Main table for all F&O instruments
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS instruments (
                instrument_key TEXT PRIMARY KEY,
                exchange TEXT,
                tradingsymbol TEXT,
                name TEXT,
                underlying_key TEXT,
                underlying_symbol TEXT,
                instrument_type TEXT,
                expiry TEXT,
                strike REAL
            )
        ''')

        # Table to store historical OI data points
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oi_datapoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument_key TEXT,
                timestamp DATETIME,
                oi INTEGER,
                FOREIGN KEY (instrument_key) REFERENCES instruments (instrument_key)
            )
        ''')

        # Table to store final calculated results
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS oi_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument_key TEXT,
                timestamp DATETIME,
                result_3m REAL,
                result_5m REAL,
                result_10m REAL,
                result_15m REAL,
                result_30m REAL,
                FOREIGN KEY (instrument_key) REFERENCES instruments (instrument_key)
            )
        ''')

        # Table for application logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS app_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                level TEXT,
                message TEXT
            )
        ''')

        # Create indexes for performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_instruments_underlying ON instruments (underlying_key)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_datapoints_instrument_time ON oi_datapoints (instrument_key, timestamp DESC)')

        print("Database initialized successfully.")

    except sqlite3.Error as e:
        print(f"Database initialization error: {e}")
    finally:
        if conn:
            conn.commit()
            conn.close()

# --- Placeholder functions ---
# These will be implemented fully in the next steps.

def get_tradable_instruments():
    """Fetches the list of unique F&O underlying symbols from the database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Query for unique underlying symbols and their keys
        cursor.execute("SELECT DISTINCT underlying_symbol, underlying_key FROM instruments WHERE underlying_symbol IS NOT NULL ORDER BY underlying_symbol")
        rows = cursor.fetchall()

        # Prepare a list of dictionaries for easy JSON conversion
        instruments = [{'name': row['underlying_symbol'], 'key': row['underlying_key']} for row in rows]

        # Manually add major indices that might not be in the F&O file as underlyings
        main_indices = [
            {'name': 'Nifty 50', 'key': 'NSE_INDEX|Nifty 50'},
            {'name': 'Nifty Bank', 'key': 'NSE_INDEX|Nifty Bank'},
            {'name': 'Sensex', 'key': 'BSE_INDEX|SENSEX'}
        ]

        # Combine lists, ensuring no duplicates
        final_list = main_indices + [inst for inst in instruments if inst['name'] not in {i['name'] for i in main_indices}]

        return final_list

    except sqlite3.Error as e:
        print(f"Database error in get_tradable_instruments: {e}")
        return [] # Return empty list on error
    finally:
        if conn:
            conn.close()

def get_available_expiry_dates(symbol_key):
    """Fetches available future expiry dates for a symbol from the local database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        # Query for future expiry dates for the given symbol's underlying_key
        # We use underlying_key to be consistent across indices and stocks
        cursor.execute("SELECT DISTINCT expiry FROM instruments WHERE underlying_key = ? AND expiry >= ? ORDER BY expiry", (symbol_key, today))
        rows = cursor.fetchall()

        return [row['expiry'] for row in rows]

    except sqlite3.Error as e:
        print(f"Database error in get_available_expiry_dates: {e}")
        return []
    finally:
        if conn:
            conn.close()

def log_oi_datapoint(instrument_key, timestamp, oi):
    """Logs a single OI data point to the database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO oi_datapoints (instrument_key, timestamp, oi) VALUES (?, ?, ?)", (instrument_key, timestamp, oi))
    except sqlite3.Error as e:
        print(f"Database error in log_oi_datapoint: {e}")
    finally:
        if conn:
            conn.commit()
            conn.close()

def store_oi_result(instrument_key, results):
    """Stores a set of calculated OI change results in the database."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO oi_results (instrument_key, timestamp, result_3m, result_5m, result_10m, result_15m, result_30m)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
        ''', (
            instrument_key,
            results.get(3, 0),
            results.get(5, 0),
            results.get(10, 0),
            results.get(15, 0),
            results.get(30, 0)
        ))
    except sqlite3.Error as e:
        print(f"Database error in store_oi_result: {e}")
    finally:
        if conn:
            conn.commit()
            conn.close()

def get_recent_oi_datapoints(instrument_key, minutes=30):
    """Retrieves the last N minutes of OI data points for an instrument."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        time_threshold = datetime.now() - timedelta(minutes=minutes)

        cursor.execute('''
            SELECT timestamp, oi FROM oi_datapoints
            WHERE instrument_key = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        ''', (instrument_key, time_threshold))

        return cursor.fetchall()

    except sqlite3.Error as e:
        print(f"Database error in get_recent_oi_datapoints: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_all_strikes_for_expiry(symbol_key, expiry_date):
    """Gets all unique strike prices for a given symbol and expiry date from the DB."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT strike FROM instruments WHERE underlying_key = ? AND expiry = ? ORDER BY strike", (symbol_key, expiry_date))
        return [row['strike'] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Database error in get_all_strikes_for_expiry: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_instrument_keys_for_strikes(symbol_key, expiry_date, strikes):
    """Gets all instrument keys for a list of strikes."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in strikes)
        query = f"SELECT instrument_key FROM instruments WHERE underlying_key = ? AND expiry = ? AND strike IN ({placeholders})"
        params = [symbol_key, expiry_date] + strikes
        cursor.execute(query, params)
        return [row['instrument_key'] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Database error in get_instrument_keys_for_strikes: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_latest_oi_results(symbol, expiry):
    """
    Gets the most recently calculated OI results for all relevant strikes
    of a given symbol and expiry.
    """
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # This is a more complex query that joins tables to get the latest result for each relevant instrument
        # It finds the max id for each instrument_key and then joins to get the data.
        query = """
            SELECT
                i.strike,
                i.instrument_type,
                r.result_3m,
                r.result_5m,
                r.result_10m,
                r.result_15m,
                r.result_30m
            FROM oi_results r
            INNER JOIN (
                SELECT instrument_key, MAX(id) as max_id
                FROM oi_results
                GROUP BY instrument_key
            ) latest ON r.instrument_key = latest.instrument_key AND r.id = latest.max_id
            JOIN instruments i ON r.instrument_key = i.instrument_key
            WHERE i.underlying_key = ? AND i.expiry = ?
        """

        cursor.execute(query, (symbol, expiry))
        rows = cursor.fetchall()

        # Process the results into the format expected by the frontend
        call_data = {}
        put_data = {}
        for row in rows:
            data_dict = {
                3: row['result_3m'],
                5: row['result_5m'],
                10: row['result_10m'],
                15: row['result_15m'],
                30: row['result_30m']
            }
            if 'CE' in row['instrument_type']:
                call_data[row['strike']] = data_dict
            elif 'PE' in row['instrument_type']:
                put_data[row['strike']] = data_dict

        return {'call_data': call_data, 'put_data': put_data}

    except sqlite3.Error as e:
        print(f"Database error in get_latest_oi_results: {e}")
        return {'call_data': {}, 'put_data': {}}
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    print("Setting up the database...")
    init_db()