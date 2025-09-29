import os
import time
import logging
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify
import upstox_client

# --- Step 1: Basic Setup ---
# Load environment variables and configure logging
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Flask App
app = Flask(__name__)

# --- Step 2: Configuration and Constants ---
# Fetch API credentials from environment
API_KEY = os.environ.get("UPSTOX_API_KEY")
API_SECRET = os.environ.get("UPSTOX_API_SECRET")
REDIRECT_URI = os.environ.get("UPSTOX_REDIRECT_URI")
ACCESS_TOKEN = os.environ.get("UPSTOX_ACCESS_TOKEN")

# Application constants
UNDERLYING_INSTRUMENT = "NSE_INDEX|Nifty 50"
STRIKE_DIFFERENCE = 50
NUM_STRIKES = 2  # Fetches ATM, 2 ITM, and 2 OTM strikes
DATA_INTERVAL = "1minute"
OI_INTERVALS_MIN = [10, 15, 30]

# --- Step 3: Global State Management ---
# Global variables for the API client and application state
api_client = None
app_state = {
    "status": "Initializing",
    "message": "Application is starting up.",
    "last_updated": None,
    "data": None
}

# ==============================================================================
# --- CORE API AND DATA LOGIC (RECONSTRUCTED WITH ALL FIXES) ---
# ==============================================================================

def initialize_api_client():
    """
    Initializes the Upstox API client using the access token from the environment.
    Verifies the connection by fetching the user profile.
    """
    global api_client
    if not ACCESS_TOKEN or "YOUR_ACCESS_TOKEN" in ACCESS_TOKEN:
        app_state.update({"status": "Error", "message": "Access token is missing or is a placeholder. Please configure it in .env."})
        logging.error(app_state["message"])
        return False

    try:
        configuration = upstox_client.Configuration()
        configuration.access_token = ACCESS_TOKEN
        api_client = upstox_client.ApiClient(configuration)

        # Verify connection
        user_api = upstox_client.UserApi(api_client)
        user_api.get_profile("v1")

        app_state.update({"status": "Initialized", "message": "API client connected. Waiting for first data fetch."})
        logging.info("Upstox API client initialized and connection verified.")
        return True
    except Exception as e:
        app_state.update({"status": "Error", "message": "Failed to initialize API client. The access token may be invalid or expired."})
        logging.error(f"{app_state['message']} Details: {e}", exc_info=True)
        api_client = None
        return False

def get_atm_strike():
    """
    Fetches the Last Traded Price (LTP) for the underlying instrument
    and calculates the At-The-Money (ATM) strike price.
    """
    try:
        quote_api = upstox_client.MarketQuoteApi(api_client)
        # FIX: Correct method is ltp()
        api_response = quote_api.ltp(UNDERLYING_INSTRUMENT, "v2")

        # FIX: Robustly parse the response to avoid KeyError
        ltp_data = list(api_response.data.values())[0]
        ltp = ltp_data.last_price

        if ltp:
            atm_strike = round(ltp / STRIKE_DIFFERENCE) * STRIKE_DIFFERENCE
            logging.info(f"NIFTY LTP: {ltp}, ATM Strike: {atm_strike}")
            return atm_strike
        else:
            logging.error("Could not fetch NIFTY 50 LTP. The value was empty.")
            return None
    except Exception as e:
        logging.error(f"Error fetching ATM strike: {e}", exc_info=True)
        return None

def get_nearest_weekly_expiry():
    """
    Fetches all option contracts for the underlying to find the nearest
    upcoming weekly expiry date.
    """
    try:
        # FIX: Correct class is OptionsApi
        options_api = upstox_client.OptionsApi(api_client)
        response = options_api.get_option_contracts(instrument_key=UNDERLYING_INSTRUMENT)

        if not response.data:
            logging.error("Could not fetch option contracts to determine expiry dates.")
            return None

        today = datetime.now().date()
        future_expiries = set()

        # FIX: Correct attribute is .expiry on the InstrumentData object
        for contract in response.data:
            if contract.expiry:
                expiry_dt = contract.expiry.date()
                if expiry_dt >= today and contract.weekly:
                    future_expiries.add(expiry_dt)

        if not future_expiries:
            logging.error("No future weekly expiry dates found from option contracts.")
            return None

        nearest_expiry_date = sorted(list(future_expiries))[0]
        logging.info(f"Automatically selected nearest weekly expiry: {nearest_expiry_date}")
        return nearest_expiry_date.strftime('%Y-%m-%d')

    except Exception as e:
        logging.error(f"Error determining nearest weekly expiry: {e}", exc_info=True)
        return None

def get_option_chain(expiry_date):
    """
    Fetches the full Put/Call option chain for a given expiry date.
    """
    try:
        # FIX: Correct class is OptionsApi and method is get_put_call_option_chain
        options_api = upstox_client.OptionsApi(api_client)
        response = options_api.get_put_call_option_chain(
            instrument_key=UNDERLYING_INSTRUMENT,
            expiry_date=expiry_date
        )
        return response.data
    except Exception as e:
        logging.error(f"Error fetching option chain for expiry {expiry_date}: {e}", exc_info=True)
        return None

def get_historical_oi(instrument_key):
    """
    Fetches 1-minute historical candle data for a given instrument key.
    """
    try:
        history_api = upstox_client.HistoryApi(api_client)
        to_date = datetime.now().date()
        from_date = to_date - timedelta(days=2)

        response = history_api.get_historical_candle_data(
            instrument_key=instrument_key,
            interval=DATA_INTERVAL,
            to_date=to_date.strftime('%Y-%m-%d'),
            from_date=from_date.strftime('%Y-%m-%d'),
            api_version="v2"
        )
        return response.data.candles
    except Exception as e:
        logging.error(f"Error fetching historical OI for '{instrument_key}': {e}", exc_info=True)
        return []

def calculate_oi_change(candles, latest_oi):
    """
    Calculates the percentage change in Open Interest over predefined intervals.
    """
    oi_changes = {}
    now = datetime.now()
    for minutes in OI_INTERVALS_MIN:
        target_time = now - timedelta(minutes=minutes)
        past_oi = None
        for candle in reversed(candles):
            candle_time = datetime.fromtimestamp(int(candle[0]) / 1000)
            if candle_time <= target_time:
                past_oi = candle[6]
                break

        if past_oi is not None and past_oi > 0:
            change_pct = ((latest_oi - past_oi) / past_oi) * 100
            oi_changes[f"chg_{minutes}m"] = round(change_pct, 2)
        else:
            oi_changes[f"chg_{minutes}m"] = 0
    return oi_changes

def process_single_option(option_data, strike_price):
    """
    A helper function to process one option contract (either a call or a put).
    """
    # FIX: The instrument_key is nested inside this PutCallOptionChainData object
    if not option_data or not option_data.instrument_key:
        return None

    instrument_key = option_data.instrument_key
    logging.info(f"Processing: {instrument_key}")

    candles = get_historical_oi(instrument_key)
    if not candles:
        return None

    latest_oi = candles[-1][6]
    changes = calculate_oi_change(candles, latest_oi)

    return {"strike": strike_price, **changes}

def update_data_in_background():
    """
    This is the main background task. It orchestrates fetching all data,
    processing it, and updating the global app_state.
    """
    if not api_client:
        return

    app_state["status"] = "Working"
    app_state["message"] = "Fetching live market data..."
    logging.info("Starting background data update...")

    try:
        atm_strike = get_atm_strike()
        if not atm_strike:
            app_state.update({"status": "Error", "message": "Could not determine ATM strike."})
            return

        nearest_expiry = get_nearest_weekly_expiry()
        if not nearest_expiry:
            app_state.update({"status": "Error", "message": "Could not automatically determine the nearest expiry date."})
            return

        app_state["message"] = f"Fetching option chain for {nearest_expiry}..."
        option_chain = get_option_chain(nearest_expiry)
        if not option_chain:
            app_state.update({"status": "Error", "message": f"Could not fetch option chain for expiry {nearest_expiry}."})
            return

        strikes_to_fetch = [atm_strike + (i * STRIKE_DIFFERENCE) for i in range(-NUM_STRIKES, NUM_STRIKES + 1)]

        processed_data = {"calls": [], "puts": [], "alert": False}
        highlighted_cells = 0
        total_cells = len(strikes_to_fetch) * len(OI_INTERVALS_MIN) * 2

        app_state["message"] = "Processing contracts..."
        # FIX: The main object in the chain is OptionStrikeData
        for strike_data in option_chain:
            if strike_data.strike_price in strikes_to_fetch:

                # FIX: Access the nested call_options object
                call_result = process_single_option(strike_data.call_options, strike_data.strike_price)
                if call_result:
                    processed_data["calls"].append(call_result)
                    if abs(call_result.get("chg_10m", 0)) > 10: highlighted_cells += 1
                    if abs(call_result.get("chg_15m", 0)) > 15: highlighted_cells += 1
                    if abs(call_result.get("chg_30m", 0)) > 25: highlighted_cells += 1

                # FIX: Access the nested put_options object
                put_result = process_single_option(strike_data.put_options, strike_data.strike_price)
                if put_result:
                    processed_data["puts"].append(put_result)
                    if abs(put_result.get("chg_10m", 0)) > 10: highlighted_cells += 1
                    if abs(put_result.get("chg_15m", 0)) > 15: highlighted_cells += 1
                    if abs(put_result.get("chg_30m", 0)) > 25: highlighted_cells += 1

        if not processed_data["calls"] and not processed_data["puts"]:
            app_state.update({"status": "Warning", "message": "Data fetched, but no matching option contracts were found for the required strikes."})
        else:
            if total_cells > 0 and (highlighted_cells / total_cells) > 0.5:
                processed_data["alert"] = True
            app_state["data"] = processed_data
            app_state["status"] = "OK"
            app_state["message"] = "Dashboard is live."
            app_state["last_updated"] = datetime.now()
            logging.info(f"Background data update finished. Highlighted cells: {highlighted_cells}/{total_cells}")

    except Exception as e:
        app_state.update({"status": "Error", "message": "A critical error occurred during the data update cycle."})
        logging.error(f"{app_state['message']} Details: {e}", exc_info=True)

def background_scheduler():
    """A simple scheduler to run the data update task every 60 seconds."""
    while True:
        update_data_in_background()
        time.sleep(60)

# ==============================================================================
# --- FLASK ROUTES ---
# ==============================================================================

@app.route("/")
def index():
    """Renders the main dashboard page."""
    return render_template("index.html")

@app.route("/status")
def status_endpoint():
    """
    Provides the current application status and data to the frontend.
    """
    return jsonify({
        "status": app_state["status"],
        "message": app_state["message"],
        "data": app_state["data"],
        "last_updated": app_state["last_updated"].strftime('%H:%M:%S') if app_state["last_updated"] else None
    })

# ==============================================================================
# --- MAIN EXECUTION ---
# ==============================================================================

if __name__ == "__main__":
    if initialize_api_client():
        logging.info("API client ready. Starting background data scheduler...")
        # Run first update immediately to populate initial data
        update_data_in_background()
        # Start the scheduler in a separate thread
        scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
        scheduler_thread.start()
    else:
        logging.error("Could not start background tasks due to API client initialization failure. The server will run to display the error.")

    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)