import upstox_client
from upstox_client.rest import ApiException
from datetime import datetime, timedelta
import pandas as pd

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

def get_oi_data(access_token, symbol, expiry):
    """The main function to fetch and process all OI data."""
    api_client = get_api_client(access_token)

    expiry_date = expiry or (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

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