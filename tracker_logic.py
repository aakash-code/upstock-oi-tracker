import upstox_client
from upstox_client.rest import ApiException
from datetime import datetime, timedelta
import pandas as pd
import sqlite3

# --- Database-backed Logic ---

def get_tradable_instruments():
    """
    Fetches the list of tradable F&O instruments directly from the local database.
    """
    try:
        conn = sqlite3.connect('instruments.db')
        cursor = conn.cursor()

        # Query for unique underlying symbols and keys
        cursor.execute("SELECT DISTINCT underlying_symbol, underlying_key FROM fno_instruments WHERE underlying_symbol IS NOT NULL ORDER BY underlying_symbol")
        rows = cursor.fetchall()

        underlyings = {row[0]: row[1] for row in rows}

        main_indices = {
            "Nifty 50": "NSE_INDEX|Nifty 50",
            "Nifty Bank": "NSE_INDEX|Nifty Bank",
            "Sensex": "BSE_INDEX|SENSEX"
        }

        # Combine and format the list
        instrument_list = [{'name': name, 'key': key} for name, key in main_indices.items()]
        for name, key in underlyings.items():
            if name not in main_indices:
                 instrument_list.append({'name': name, 'key': key})

        return instrument_list

    except sqlite3.Error as e:
        print(f"Database error in get_tradable_instruments: {e}. Falling back to a hardcoded list.")
        return [
            {'name': 'Nifty 50', 'key': 'NSE_INDEX|Nifty 50'},
            {'name': 'Nifty Bank', 'key': 'NSE_INDEX|Nifty Bank'},
            {'name': 'Sensex', 'key': 'BSE_INDEX|SENSEX'},
        ]
    finally:
        if conn:
            conn.close()

def get_available_expiry_dates(symbol_key):
    """Fetches available future expiry dates for a symbol from the local database."""
    try:
        conn = sqlite3.connect('instruments.db')
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        # Query for future expiry dates for the given symbol
        cursor.execute("SELECT DISTINCT expiry FROM fno_instruments WHERE underlying_key = ? AND expiry >= ? ORDER BY expiry", (symbol_key, today))
        rows = cursor.fetchall()

        return [row[0] for row in rows]

    except sqlite3.Error as e:
        print(f"Database error in get_available_expiry_dates: {e}")
        return []
    finally:
        if conn:
            conn.close()

# --- API-based Logic (for live data) ---

def get_api_client(access_token):
    """Creates and returns an Upstox API client instance."""
    configuration = upstox_client.Configuration()
    configuration.access_token = access_token
    return upstox_client.ApiClient(configuration)

def get_ltp(api_client, instrument_key):
    """Fetches the Last Traded Price (LTP) for a given instrument key."""
    api_instance = upstox_client.MarketQuoteApi(api_client)
    try:
        api_response = api_instance.ltp(instrument_key, "v2")
        instrument_key_for_dict = instrument_key.replace('|', ':')
        return api_response.data[instrument_key_for_dict].last_price
    except ApiException as e:
        print(f"Error fetching LTP for {instrument_key}: {e}")
        return None

def get_historical_oi_data(api_client, instrument_key, interval='1minute'):
    """Fetches historical Open Interest (OI) data for a given instrument key."""
    history_api = upstox_client.HistoryApi(api_client)
    to_date = datetime.now().strftime('%Y-%m-%d')
    try:
        api_response = history_api.get_intra_day_candle_data1(instrument_key, interval, "v2")
        return api_response.data.candles
    except ApiException as e:
        print(f"Error fetching historical OI for {instrument_key}: {e}")
        return None

# --- Main Data Processing ---

def find_atm_strike(ltp, strikes):
    """Finds the At-The-Money (ATM) strike price."""
    return min(strikes, key=lambda x: abs(x - ltp))

def get_relevant_strikes(atm_strike, strikes):
    """Gets the ATM, 3 ITM, and 3 OTM strikes."""
    strikes.sort()
    try:
        atm_index = strikes.index(atm_strike)
        start_index = max(0, atm_index - 3)
        end_index = min(len(strikes), atm_index + 4)
        return strikes[start_index:end_index]
    except (ValueError, IndexError):
        return []

def calculate_oi_change(initial_oi, current_oi):
    """Calculates the percentage change in Open Interest."""
    if initial_oi is None or current_oi is None or initial_oi == 0:
        return 0.0
    return ((current_oi - initial_oi) / initial_oi) * 100

def get_oi_data(access_token, symbol, expiry_date):
    """The main function to fetch and process all OI data, using the local database."""
    api_client = get_api_client(access_token)

    if not expiry_date:
        available_expiries = get_available_expiry_dates(symbol)
        if not available_expiries:
            print(f"Could not find any available expiry dates for {symbol}.")
            return None
        expiry_date = available_expiries[0]

    ltp = get_ltp(api_client, symbol)
    if ltp is None:
        return None

    try:
        conn = sqlite3.connect('instruments.db')
        cursor = conn.cursor()

        # Get all strikes for the selected symbol and expiry
        cursor.execute("SELECT DISTINCT strike FROM fno_instruments WHERE underlying_key = ? AND expiry = ? ORDER BY strike", (symbol, expiry_date))
        all_strikes = [row[0] for row in cursor.fetchall()]

        if not all_strikes:
            print(f"No strikes found in DB for {symbol} on {expiry_date}")
            return None

        atm_strike = find_atm_strike(ltp, all_strikes)
        relevant_strikes = get_relevant_strikes(atm_strike, all_strikes)

        # Get instrument keys for the relevant strikes directly from the DB
        placeholders = ','.join('?' for _ in relevant_strikes)
        cursor.execute(f"SELECT strike, instrument_key, instrument_type FROM fno_instruments WHERE underlying_key = ? AND expiry = ? AND strike IN ({placeholders})", [symbol, expiry_date] + relevant_strikes)
        rows = cursor.fetchall()

        call_instruments = {row[0]: row[1] for row in rows if row[2] == 'OPTIDX' or row[2] == 'OPTSTK'}
        put_instruments = {row[0]: row[1] for row in rows if row[2] == 'OPTIDX' or row[2] == 'OPTSTK'}

        # Note: The above logic incorrectly assigns the same key to both call and put.
        # A proper schema would differentiate them. For now, we'll assume the API calls handle it.
        # A better DB query would be needed for a perfect system.
        # Let's refine the instrument key fetching
        call_instruments = {row[0]: row[1] for row in rows if 'CE' in row[1]}
        put_instruments = {row[0]: row[1] for row in rows if 'PE' in row[1]}


    except sqlite3.Error as e:
        print(f"Database error in get_oi_data: {e}")
        return None
    finally:
        if conn:
            conn.close()

    call_table_data = {}
    put_table_data = {}
    time_intervals = [3, 5, 10, 15, 30]

    for strike_price in relevant_strikes:
        # Process Call options
        if strike_price in call_instruments:
            instrument_key = call_instruments[strike_price]
            all_candles = get_historical_oi_data(api_client, instrument_key)
            if all_candles:
                df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('timestamp')

                if not df.empty:
                    current_candle = df.iloc[-1]
                    current_oi = current_candle['oi']

                    changes = {}
                    for minutes_ago in time_intervals:
                        target_time = current_candle.name - timedelta(minutes=minutes_ago)
                        past_candle_index = df.index.get_indexer([target_time], method='nearest')
                        if past_candle_index[0] != -1:
                            past_candle = df.iloc[past_candle_index[0]]
                            initial_oi = past_candle['oi']
                            changes[minutes_ago] = calculate_oi_change(initial_oi, current_oi)

                    call_table_data[strike_price] = changes

        # Process Put options
        if strike_price in put_instruments:
            instrument_key = put_instruments[strike_price]
            all_candles = get_historical_oi_data(api_client, instrument_key)
            if all_candles:
                df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.set_index('timestamp')

                if not df.empty:
                    current_candle = df.iloc[-1]
                    current_oi = current_candle['oi']

                    changes = {}
                    for minutes_ago in time_intervals:
                        target_time = current_candle.name - timedelta(minutes=minutes_ago)
                        past_candle_index = df.index.get_indexer([target_time], method='nearest')
                        if past_candle_index[0] != -1:
                            past_candle = df.iloc[past_candle_index[0]]
                            initial_oi = past_candle['oi']
                            changes[minutes_ago] = calculate_oi_change(initial_oi, current_oi)

                    put_table_data[strike_price] = changes

    return call_table_data, put_table_data