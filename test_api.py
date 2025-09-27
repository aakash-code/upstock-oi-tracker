import upstox_client
from upstox_client.rest import ApiException
import os
from datetime import datetime

# --- Configuration ---
API_KEY = os.environ.get("UPSTOX_API_KEY", "YOUR_API_KEY")
ACCESS_TOKEN = os.environ.get("UPSTOX_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")
underlying_instrument = "NSE_INDEX|Nifty 50"
test_option_instrument = "NSE_FO|52265" # A sample Nifty option, may need to be updated if expired

def get_api_client():
    """Creates and returns an Upstox API client instance."""
    configuration = upstox_client.Configuration()
    configuration.access_token = ACCESS_TOKEN
    api_client = upstox_client.ApiClient(configuration)
    return api_client

def test_get_ltp(api_client, instrument_key):
    """Tests the get_ltp API call."""
    print(f"[{datetime.now()}] --- Testing get_ltp ---")
    api_instance = upstox_client.MarketQuoteApi(api_client)
    try:
        api_response = api_instance.ltp(instrument_key, "v2")
        print(f"[{datetime.now()}] get_ltp response: {api_response}")
    except ApiException as e:
        print(f"[{datetime.now()}] Error in get_ltp: {e}")
    print(f"[{datetime.now()}] --- Finished testing get_ltp ---")


def test_get_option_chain(api_client, instrument_key):
    """Tests the get_option_chain API call."""
    print(f"[{datetime.now()}] --- Testing get_option_chain ---")
    api_instance = upstox_client.OptionsApi(api_client)
    try:
        api_response = api_instance.get_put_call_option_chain(instrument_key, "2025-12-31")
        print(f"[{datetime.now()}] get_option_chain response received.")
    except ApiException as e:
        print(f"[{datetime.now()}] Error in get_option_chain: {e}")
    print(f"[{datetime.now()}] --- Finished testing get_option_chain ---")


def test_get_historical_data(api_client, instrument_key):
    """Tests the get_historical_oi_data API call."""
    print(f"[{datetime.now()}] --- Testing get_historical_data ---")
    history_api = upstox_client.HistoryApi(api_client)
    to_date = datetime.now().strftime('%Y-%m-%d')
    try:
        api_response = history_api.get_intra_day_candle_data1(instrument_key, '1minute', "v2")
        print(f"[{datetime.now()}] get_historical_data response received.")
    except ApiException as e:
        print(f"[{datetime.now()}] Error in get_historical_data: {e}")
    print(f"[{datetime.now()}] --- Finished testing get_historical_data ---")


if __name__ == "__main__":
    print(f"[{datetime.now()}] Starting API call tests...")
    client = get_api_client()

    test_get_ltp(client, underlying_instrument)
    test_get_option_chain(client, underlying_instrument)
    test_get_historical_data(client, test_option_instrument)

    print(f"[{datetime.now()}] All API call tests complete.")