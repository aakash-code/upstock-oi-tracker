import os
import time
import logging
import upstox_client
from flask import Flask, render_template, jsonify
from datetime import datetime, timedelta, date
import threading
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Basic Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Upstox API Configuration ---
API_KEY = os.environ.get("UPSTOX_API_KEY")
API_SECRET = os.environ.get("UPSTOX_API_SECRET")
REDIRECT_URI = os.environ.get("UPSTOX_REDIRECT_URI")
ACCESS_TOKEN = os.environ.get("UPSTOX_ACCESS_TOKEN")

# --- Globals ---
api_client = None
app_state = {
    "status": "Initializing",
    "message": "Application is starting up.",
    "last_updated": None,
    "data": None
}

# --- Constants ---
UNDERLYING_INSTRUMENT = "NSE_INDEX|Nifty 50"
STRIKE_DIFFERENCE = 50
NUM_STRIKES = 2  # 2 ITM, 2 OTM, 1 ATM = 5 total
DATA_INTERVAL = "1minute"
OI_INTERVALS_MIN = [10, 15, 30]

# ==============================================================================
# --- Upstox API & Data Logic ---
# ==============================================================================

def initialize_api_client():
    """Initializes the Upstox API client and verifies the connection."""
    global api_client
    if not ACCESS_TOKEN or ACCESS_TOKEN == "YOUR_ACCESS_TOKEN":
        app_state.update({"status": "Error", "message": "Access token is missing. Please configure it in .env."})
        logging.error(app_state["message"])
        return False

    try:
        configuration = upstox_client.Configuration()
        configuration.access_token = ACCESS_TOKEN
        api_client = upstox_client.ApiClient(configuration)
        user_api = upstox_client.UserApi(api_client)
        user_api.get_profile("v1")
        app_state.update({"status": "Initialized", "message": "API client initialized. Waiting for first data fetch."})
        logging.info("Upstox API client initialized and connection verified.")
        return True
    except Exception as e:
        app_state.update({"status": "Error", "message": "Failed to initialize API client. The access token may be invalid or expired."})
        logging.error(f"{app_state['message']} Details: {e}", exc_info=True)
        api_client = None
        return False

def get_option_chain(expiry_date):
    """Fetches the option chain for a specific expiry date."""
    try:
        option_chain_api = upstox_client.OptionChainApi(api_client)
        response = option_chain_api.get_option_chain(
            api_version="v2",
            instrument_key=UNDERLYING_INSTRUMENT,
            expiry_date=expiry_date
        )
        return response.data
    except Exception as e:
        logging.error(f"Error fetching option chain for expiry {expiry_date}: {e}", exc_info=True)
        return None

def get_historical_oi(instrument_key, to_date, from_date):
    """Fetches historical OI data for a given instrument."""
    try:
        history_api = upstox_client.HistoryApi(api_client)
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
    """Calculates OI percentage change for different time intervals."""
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

def update_oi_data():
    """The core logic to fetch, process, and cache the OI data."""
    if not api_client:
        return

    app_state["status"] = "Fetching Data"
    logging.info("Starting background data update...")

    try:
        # 1. Get ATM Strike
        quote_api = upstox_client.MarketQuoteApi(api_client)
        # CORRECTED METHOD: The original `get_market_quote` was incorrect. The correct method is `ltp`.
        api_response = quote_api.ltp(UNDERLYING_INSTRUMENT, "v2")
        # FINAL FIX: The response is a dictionary keyed by the instrument. Instead of guessing the key,
        # we will access the first value in the dictionary, which is the data object we need.
        ltp_data = list(api_response.data.values())[0]
        ltp = ltp_data.last_price
        if not ltp:
            app_state.update({"status": "Error", "message": "Could not fetch NIFTY LTP."})
            logging.error(app_state["message"])
            return
        atm_strike = round(ltp / STRIKE_DIFFERENCE) * STRIKE_DIFFERENCE
        logging.info(f"NIFTY LTP: {ltp}, ATM Strike: {atm_strike}")

        # 2. Get nearest weekly expiry from option contracts
        today = date.today()
        # Simplified expiry logic: assume nearest Thursday
        days_to_thursday = (3 - today.weekday() + 7) % 7
        nearest_expiry = (today + timedelta(days=days_to_thursday)).strftime('%Y-%m-%d')

        # 3. Get Option Chain for that expiry
        option_chain = get_option_chain(nearest_expiry)
        if not option_chain:
            app_state.update({"status": "Error", "message": f"Could not fetch option chain for expiry {nearest_expiry}."})
            return

        # 4. Find relevant strikes and their instrument keys
        strikes_to_fetch = [atm_strike + (i * STRIKE_DIFFERENCE) for i in range(-NUM_STRIKES, NUM_STRIKES + 1)]

        processed_data = {"calls": [], "puts": [], "alert": False}
        highlighted_cells = 0
        total_cells = len(strikes_to_fetch) * len(OI_INTERVALS_MIN) * 2

        to_date = datetime.now()
        from_date = to_date - timedelta(days=2)

        for contract in option_chain:
            if contract.strike_price in strikes_to_fetch:
                instrument_key = contract.instrument_key
                option_type = contract.option_type
                strike_price = contract.strike_price

                logging.info(f"Processing: {instrument_key}")
                candles = get_historical_oi(instrument_key, to_date, from_date)

                if candles:
                    latest_oi = candles[-1][6]
                    changes = calculate_oi_change(candles, latest_oi)

                    table = "calls" if option_type == "CE" else "puts"
                    processed_data[table].append({"strike": strike_price, **changes})

                    if abs(changes.get("chg_10m", 0)) > 10: highlighted_cells += 1
                    if abs(changes.get("chg_15m", 0)) > 15: highlighted_cells += 1
                    if abs(changes.get("chg_30m", 0)) > 25: highlighted_cells += 1

        if not processed_data["calls"] and not processed_data["puts"]:
            app_state.update({"status": "Warning", "message": "Data fetched, but no matching option contracts were found in the chain."})
            logging.warning(app_state["message"])
        else:
            if total_cells > 0 and (highlighted_cells / total_cells) > 0.5:
                processed_data["alert"] = True
            app_state["data"] = processed_data
            app_state["status"] = "OK"
            app_state["message"] = f"Data updated successfully at {datetime.now().strftime('%H:%M:%S')}."
            app_state["last_updated"] = datetime.now()
            logging.info(f"Background data update finished. Highlighted cells: {highlighted_cells}/{total_cells}")

    except Exception as e:
        app_state.update({"status": "Error", "message": "A critical error occurred during data update."})
        logging.error(f"{app_state['message']} Details: {e}", exc_info=True)


def background_scheduler():
    """Periodically triggers the data update."""
    while True:
        update_oi_data()
        time.sleep(60)

# ==============================================================================
# --- Flask Routes ---
# ==============================================================================

@app.route("/")
def index():
    """Renders the main dashboard page."""
    return render_template("index.html")

@app.route("/status")
def status_endpoint():
    """Provides the current application status and data to the frontend."""
    return jsonify({
        "status": app_state["status"],
        "message": app_state["message"],
        "data": app_state["data"],
        "last_updated": app_state["last_updated"].strftime('%H:%M:%S') if app_state["last_updated"] else None
    })

# ==============================================================================
# --- Main Execution ---
# ==============================================================================

if __name__ == "__main__":
    if initialize_api_client():
        logging.info("API client ready. Starting background data scheduler...")
        # Run first update immediately
        update_oi_data()
        scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
        scheduler_thread.start()
    else:
        logging.error("Could not start background tasks due to API client initialization failure.")

    app.run(host='0.0.0.0', port=5000, debug=False)