import upstox_client
from upstox_client.rest import ApiException
import database
from datetime import datetime, timedelta
import pandas as pd

# --- API Client ---

def get_api_client(access_token):
    """Creates and returns an Upstox API client instance."""
    configuration = upstox_client.Configuration()
    configuration.access_token = access_token
    return upstox_client.ApiClient(configuration)

# --- Data Fetching and Storage ---

def fetch_and_store_oi_data(api_client, instrument_key):
    """
    Fetches the latest OI data for a single instrument and stores it in the database.
    """
    history_api = upstox_client.HistoryApi(api_client)
    to_date = datetime.now().strftime('%Y-%m-%d')

    try:
        # Corrected the function name from get_intra_day_candle_data1 to get_intra_day_candle_data
        api_response = history_api.get_intra_day_candle_data(instrument_key, '1minute', to_date, "v2")
        candles = api_response.data.candles
        if candles:
            latest_candle = candles[-1]
            timestamp = datetime.strptime(latest_candle[0], '%Y-%m-%dT%H:%M:%S%z')
            oi = latest_candle[6]
            database.log_oi_datapoint(instrument_key, timestamp, oi)
            print(f"Logged OI for {instrument_key}: {oi} at {timestamp}")
            return True
    except ApiException as e:
        print(f"API error fetching OI for {instrument_key}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred in fetch_and_store_oi_data: {e}")
    return False

# --- Calculation Logic ---

def calculate_oi_change(initial_oi, current_oi):
    """Calculates the percentage change in Open Interest."""
    if initial_oi is None or current_oi is None or initial_oi == 0:
        return 0.0
    return ((current_oi - initial_oi) / initial_oi) * 100

def perform_oi_calculations(instrument_key):
    """
    Retrieves historical data from the database for an instrument,
    calculates the OI change over different intervals, and stores the result.
    """
    try:
        datapoints = database.get_recent_oi_datapoints(instrument_key, minutes=35) # Fetch a bit extra
        if not datapoints or len(datapoints) < 2:
            # Not enough data to calculate change
            return

        df = pd.DataFrame(datapoints, columns=['timestamp', 'oi'])
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')

        current_candle = df.iloc[0] # Most recent is first due to ORDER BY DESC
        current_oi = current_candle['oi']

        results = {}
        time_intervals = [3, 5, 10, 15, 30]

        for minutes_ago in time_intervals:
            target_time = current_candle.name - timedelta(minutes=minutes_ago)
            # Find the nearest data point in the DataFrame
            past_candle_index = df.index.get_indexer([target_time], method='nearest')
            if past_candle_index[0] != -1:
                past_candle = df.iloc[past_candle_index[0]]
                initial_oi = past_candle['oi']
                results[minutes_ago] = calculate_oi_change(initial_oi, current_oi)

        database.store_oi_result(instrument_key, results)
        print(f"Stored new calculation for {instrument_key}")

    except Exception as e:
        print(f"An error occurred in perform_oi_calculations for {instrument_key}: {e}")

# --- Main Orchestrator for Background Worker ---

def get_ltp(api_client, instrument_key):
    """Fetches the LTP for a given instrument key."""
    api_instance = upstox_client.MarketQuoteApi(api_client)
    try:
        api_response = api_instance.ltp(instrument_key, "v2")
        instrument_key_for_dict = instrument_key.replace('|', ':')
        return api_response.data[instrument_key_for_dict].last_price
    except ApiException as e:
        print(f"Error fetching LTP for {instrument_key}: {e}")
        return None

def find_atm_strike(ltp, strikes):
    """Finds the At-The-Money (ATM) strike price."""
    return min(strikes, key=lambda x: abs(x - ltp))

def get_relevant_strikes(atm_strike, all_strikes):
    """Gets the ATM, 3 ITM, and 3 OTM strikes."""
    all_strikes.sort()
    try:
        atm_index = all_strikes.index(atm_strike)
        start_index = max(0, atm_index - 3)
        end_index = min(len(all_strikes), atm_index + 4)
        return all_strikes[start_index:end_index]
    except (ValueError, IndexError):
        return []

def update_tracked_instruments(access_token, symbol_key, expiry_date):
    """
    The main background task function. It determines which instruments to track
    based on the current market price and triggers data fetching and calculation.
    """
    print(f"--- Starting background update for {symbol_key} on {expiry_date} ---")
    api_client = get_api_client(access_token)

    # 1. Get LTP to find the ATM strike
    ltp = get_ltp(api_client, symbol_key)
    if ltp is None:
        print("Could not get LTP. Aborting update cycle.")
        return

    # 2. Get all strikes for the expiry from our database
    all_strikes = database.get_all_strikes_for_expiry(symbol_key, expiry_date)
    if not all_strikes:
        print(f"No strikes found in DB for {symbol_key} on {expiry_date}. Aborting.")
        return

    # 3. Determine the relevant strikes to track (ATM +/- 3)
    atm_strike = find_atm_strike(ltp, all_strikes)
    relevant_strikes = get_relevant_strikes(atm_strike, all_strikes)
    print(f"LTP: {ltp}, ATM Strike: {atm_strike}, Tracking {len(relevant_strikes)} strikes.")

    # 4. Get the instrument keys for these strikes from our database
    instrument_keys = database.get_instrument_keys_for_strikes(symbol_key, expiry_date, relevant_strikes)

    # 5. For each instrument, fetch new data and perform calculations
    for key in instrument_keys:
        if fetch_and_store_oi_data(api_client, key):
            perform_oi_calculations(key)

    print(f"--- Background update for {symbol_key} on {expiry_date} complete ---")