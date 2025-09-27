import upstox_client
from upstox_client.rest import ApiException
from datetime import datetime, timedelta
import pandas as pd
import urllib.request
import gzip
import json
import io

# --- Cache for instruments ---
instrument_cache = None

def get_tradable_instruments():
    """
    Fetches and filters all tradable F&O instruments from the Upstox instruments list using the NFO JSON file.
    Caches the result in memory to avoid repeated downloads.
    """
    global instrument_cache
    if instrument_cache is not None:
        return instrument_cache

    try:
        INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NFO.json.gz"

        with urllib.request.urlopen(INSTRUMENTS_URL) as response:
            compressed_file = io.BytesIO(response.read())
            with gzip.GzipFile(fileobj=compressed_file, mode='r') as decompressed_file:
                data = json.load(decompressed_file)

            underlyings = {row.get('underlying_symbol'): row.get('underlying_key') for row in data if row.get('instrument_type') == 'OPTSTK' and row.get('underlying_symbol')}

            main_indices = {
                "Nifty 50": "NSE_INDEX|Nifty 50",
                "Nifty Bank": "NSE_INDEX|Nifty Bank",
                "Sensex": "BSE_INDEX|SENSEX"
            }

            instrument_list = [{'name': name, 'key': key} for name, key in main_indices.items()]
            for name, key in sorted(underlyings.items()):
                if name not in main_indices:
                     instrument_list.append({'name': name, 'key': key})

            instrument_cache = instrument_list
            return instrument_cache

    except Exception as e:
        print(f"Error fetching dynamic tradable instruments: {e}. Falling back to a hardcoded list.")
        instrument_cache = [
            {'name': 'Nifty 50', 'key': 'NSE_INDEX|Nifty 50'},
            {'name': 'Nifty Bank', 'key': 'NSE_INDEX|Nifty Bank'},
            {'name': 'Sensex', 'key': 'BSE_INDEX|SENSEX'},
        ]
        return instrument_cache

def get_api_client(access_token):
    """Creates and returns an Upstox API client instance."""
    configuration = upstox_client.Configuration()
    configuration.access_token = access_token
    return upstox_client.ApiClient(configuration)

def get_available_expiry_dates(api_client, instrument_key):
    """Fetches all available expiry dates for a given instrument and filters for future dates."""
    api_instance = upstox_client.ExpiredInstrumentApi(api_client)
    try:
        api_response = api_instance.get_expiries(instrument_key)
        if not api_response.data:
            return []

        # Filter for dates that are today or in the future
        today = datetime.now().date()
        future_dates = [d for d in api_response.data if datetime.strptime(d, '%Y-%m-%d').date() >= today]
        return sorted(future_dates)

    except ApiException as e:
        print(f"Error fetching expiry dates for {instrument_key}: {e}")
        return []

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

def get_option_chain(api_client, instrument_key, expiry):
    """Fetches the option chain for a given instrument key and expiry."""
    api_instance = upstox_client.OptionsApi(api_client)
    try:
        api_response = api_instance.get_put_call_option_chain(instrument_key, expiry)
        return api_response.data
    except ApiException as e:
        print(f"Error fetching option chain for {instrument_key} on {expiry}: {e}")
        return None

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

def calculate_oi_change(initial_oi, current_oi):
    """Calculates the percentage change in Open Interest."""
    if initial_oi is None or current_oi is None or initial_oi == 0:
        return 0.0
    return ((current_oi - initial_oi) / initial_oi) * 100

def get_oi_data(access_token, symbol, expiry_date):
    """The main function to fetch and process all OI data."""
    api_client = get_api_client(access_token)

    if not expiry_date:
        # If no expiry is provided, fetch all and use the first one (nearest)
        available_expiries = get_available_expiry_dates(api_client, symbol)
        if not available_expiries:
            print(f"Could not find any available expiry dates for {symbol}.")
            return None
        expiry_date = available_expiries[0]

    ltp = get_ltp(api_client, symbol)
    if ltp is None:
        return None

    option_chain = get_option_chain(api_client, symbol, expiry_date)
    if not option_chain or not hasattr(option_chain[0], 'put_options') or not option_chain[0].put_options:
        print(f"Could not get a valid option chain for {symbol} on {expiry_date}")
        return None

    all_strikes = sorted(list(set([strike.strike_price for strike in option_chain[0].put_options])))
    atm_strike = find_atm_strike(ltp, all_strikes)
    relevant_strikes = get_relevant_strikes(atm_strike, all_strikes)

    call_instruments = {s.strike_price: s.instrument_key for s in option_chain[0].call_options if s.strike_price in relevant_strikes}
    put_instruments = {s.strike_price: s.instrument_key for s in option_chain[0].put_options if s.strike_price in relevant_strikes}

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