import upstox_client
from upstox_client.rest import ApiException
from datetime import datetime
import pandas as pd

# --- Constants ---
underlying_instrument = "NSE_INDEX|Nifty 50"
# Hardcoded expiry for simplicity. In a real application, this should be dynamic.
expiry_date = "2025-12-31"

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
        print(f"Error fetching LTP: {e}")
        return None

def get_option_chain(api_client, instrument_key, expiry):
    """Fetches the option chain for a given instrument key and expiry."""
    api_instance = upstox_client.OptionsApi(api_client)
    try:
        api_response = api_instance.get_put_call_option_chain(instrument_key, expiry)
        return api_response.data
    except ApiException as e:
        print(f"Error fetching option chain for {expiry}: {e}")
        return None

def find_atm_strike(ltp, strikes):
    """Finds the At-The-Money (ATM) strike price."""
    return min(strikes, key=lambda x: abs(x - ltp))

def get_relevant_strikes(atm_strike, strikes):
    """Gets the ATM, 2 ITM, and 2 OTM strikes."""
    strikes.sort()
    try:
        atm_index = strikes.index(atm_strike)
        start_index = max(0, atm_index - 2)
        end_index = min(len(strikes), atm_index + 3)
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

def get_oi_data(access_token):
    """The main function to fetch and process all OI data."""
    api_client = get_api_client(access_token)

    ltp = get_ltp(api_client, underlying_instrument)
    if not ltp:
        return None

    option_chain = get_option_chain(api_client, underlying_instrument, expiry_date)
    if not option_chain:
        return None

    all_strikes = sorted(list(set([strike.strike_price for strike in option_chain[0].put_options])))
    atm_strike = find_atm_strike(ltp, all_strikes)
    relevant_strikes = get_relevant_strikes(atm_strike, all_strikes)

    call_instruments = {s.strike_price: s.instrument_key for s in option_chain[0].call_options if s.strike_price in relevant_strikes}
    put_instruments = {s.strike_price: s.instrument_key for s in option_chain[0].put_options if s.strike_price in relevant_strikes}

    # Using a single data store for simplicity in this context
    oi_data_store = {}
    current_time = datetime.now()

    for strike_price in relevant_strikes:
        for option_type, instruments in [("call", call_instruments), ("put", put_instruments)]:
            if strike_price in instruments:
                instrument_key = instruments[strike_price]

                if instrument_key not in oi_data_store:
                    oi_data_store[instrument_key] = {'type': option_type, 'strike': strike_price, 'data': []}

                oi_data = get_historical_oi_data(api_client, instrument_key)
                if oi_data:
                    latest_oi = oi_data[-1][6]
                    # For a web app, we'd typically use a proper database or cache
                    # Here we just append to a list for one-time calculation
                    oi_data_store[instrument_key]['data'].append((current_time, latest_oi))

    # --- Process Data for Display ---
    call_table_data = {}
    put_table_data = {}

    for key, value in oi_data_store.items():
        changes = {}
        # In a real app, you would fetch and compare against stored historical data
        # For this example, we'll simulate by just showing the latest OI
        # The logic for 10, 15, 30 min changes would require a persistent data store
        # which is beyond the scope of this refactoring.
        # We will just return the latest OI for now.
        latest_oi = value['data'][-1][1] if value['data'] else 0
        changes = {'10': latest_oi, '15': latest_oi, '30': latest_oi} # Placeholder

        if value['type'] == 'call':
            call_table_data[value['strike']] = changes
        else:
            put_table_data[value['strike']] = changes

    return call_table_data, put_table_data