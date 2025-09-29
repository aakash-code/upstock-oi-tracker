import os
import time
import logging
import upstox_client
from flask import Flask, render_template, jsonify, request
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

# Global variable for the Upstox API client
api_client = None

# --- Constants ---
UNDERLYING_SYMBOL = "NIFTY"
INSTRUMENT_TYPE = "FFO"
EXCHANGE = "NSE_FO"
STRIKE_DIFFERENCE = 50
NUM_STRIKES = 2  # 2 ITM, 2 OTM, 1 ATM = 5 total
DATA_INTERVAL = "1minute"
OI_INTERVALS_MIN = [10, 15, 30]

# --- In-memory cache ---
cache = {
    "instruments": None,
    "expiry": None,
    "data": None,
    "last_updated": None
}

# ==============================================================================
# --- Upstox API Helper Functions ---
# ==============================================================================

def initialize_api_client():
    """Initializes the Upstox API client with the access token."""
    global api_client
    if not ACCESS_TOKEN:
        logging.error("UPSTOX_ACCESS_TOKEN is not set in the environment.")
        return False

    try:
        configuration = upstox_client.Configuration()
        configuration.access_token = ACCESS_TOKEN
        api_client = upstox_client.ApiClient(configuration)
        # Verify connection by making a simple API call
        user_api = upstox_client.UserApi(api_client)
        user_api.get_profile("v1")
        logging.info("Upstox API client initialized and connection verified.")
        return True
    except Exception as e:
        logging.error(f"Failed to initialize or verify API client: {e}")
        api_client = None # Ensure client is None on failure
        return False

def get_atm_strike():
    """Fetches LTP for NIFTY 50 to determine the ATM strike."""
    try:
        quote_api = upstox_client.MarketQuoteApi(api_client)
        nifty_instrument_key = "NSE_INDEX|Nifty 50"
        api_response = quote_api.get_market_quote(nifty_instrument_key, "v1")
        ltp = api_response.data.last_price
        if ltp:
            atm_strike = round(ltp / STRIKE_DIFFERENCE) * STRIKE_DIFFERENCE
            logging.info(f"NIFTY 50 LTP: {ltp}, ATM Strike: {atm_strike}")
            return atm_strike
        else:
            logging.warning("Could not fetch NIFTY 50 LTP.")
            return None
    except Exception as e:
        logging.error(f"Error fetching ATM strike: {e}")
        return None

def get_nearest_weekly_expiry():
    """Determines the nearest weekly expiry date (simplified)."""
    if cache["expiry"] is None:
        today = date.today()
        days_to_thursday = (3 - today.weekday() + 7) % 7
        expiry = today + timedelta(days=days_to_thursday)
        if expiry < today:
             expiry += timedelta(weeks=1)
        cache["expiry"] = expiry
        logging.info(f"Calculated nearest weekly expiry: {cache['expiry']}")
    return cache["expiry"]

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
        logging.error(f"Error fetching historical OI for {instrument_key}: {e}")
        return []

def format_instrument_key(expiry, strike, option_type):
    """Formats the Upstox instrument key for an options contract."""
    expiry_str = expiry.strftime('%y%m%d')
    return f"{EXCHANGE}|{UNDERLYING_SYMBOL}{expiry_str}{strike}{option_type}"

# ==============================================================================
# --- Data Processing and Analysis ---
# ==============================================================================

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
        logging.warning("API client not available. Skipping data update.")
        return

    logging.info("Starting background data update...")

    atm_strike = get_atm_strike()
    expiry_date = get_nearest_weekly_expiry()
    if not atm_strike or not expiry_date:
        logging.error("Could not determine ATM strike or expiry. Aborting update.")
        return

    strikes = [atm_strike + (i * STRIKE_DIFFERENCE) for i in range(-NUM_STRIKES, NUM_STRIKES + 1)]

    processed_data = {"calls": [], "puts": [], "alert": False}
    highlighted_cells = 0
    total_cells = len(strikes) * len(OI_INTERVALS_MIN) * 2

    to_date = datetime.now()
    from_date = to_date - timedelta(days=2) # Fetch data for the last 2 days

    for strike in strikes:
        for opt_type in ["CE", "PE"]:
            key = format_instrument_key(expiry_date, strike, opt_type)
            candles = get_historical_oi(key, to_date, from_date)
            if candles:
                latest_oi = candles[-1][6]
                changes = calculate_oi_change(candles, latest_oi)

                table = "calls" if opt_type == "CE" else "puts"
                processed_data[table].append({"strike": strike, **changes})

                if abs(changes.get("chg_10m", 0)) > 10: highlighted_cells += 1
                if abs(changes.get("chg_15m", 0)) > 15: highlighted_cells += 1
                if abs(changes.get("chg_30m", 0)) > 25: highlighted_cells += 1

    if total_cells > 0 and (highlighted_cells / total_cells) > 0.5:
        processed_data["alert"] = True

    cache["data"] = processed_data
    cache["last_updated"] = datetime.now()
    logging.info(f"Background data update finished. Highlighted cells: {highlighted_cells}/{total_cells}")

def background_scheduler():
    """Periodically triggers the data update."""
    while True:
        update_oi_data()
        time.sleep(60)

# ==============================================================================
# --- Flask Routes ---
# ==============================================================================

@app.route("/login")
def login():
    """Provides instructions and link to log in to Upstox."""
    if not all([API_KEY, API_SECRET, REDIRECT_URI]):
        return "Error: Please set UPSTOX_API_KEY, UPSTOX_API_SECRET, and UPSTOX_REDIRECT_URI in your .env file.", 500

    login_url = f"https://api-v2.upstox.com/login/authorization/dialog?response_type=code&client_id={API_KEY}&redirect_uri={REDIRECT_URI}"

    return f"""
    <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Login to Upstox</title>
    <style>body{{font-family:sans-serif;line-height:1.6;padding:2em;background-color:#f4f4f4;}}pre{{background-color:#eee;padding:1em;border-radius:5px;white-space:pre-wrap;word-wrap:break-word;}}a{{color:#0077cc;}}</style></head>
    <body><h1>Step 1: Authorize Application</h1><p>Click the link below to log in and authorize.</p>
    <p><a href="{login_url}" target="_blank"><strong>Authorize with Upstox</strong></a></p><hr>
    <h1>Step 2: Get Access Token</h1><p>After authorization, you'll be redirected to a URL with a code. Copy it.</p>
    <p>Use the cURL command below in your terminal to get an access token. Replace <code>YOUR_AUTH_CODE</code> with your code.</p>
    <pre>curl -X POST "https://api-v2.upstox.com/login/authorization/token" \
-H "Content-Type: application/x-www-form-urlencoded" -H "Accept: application/json" \
-d "code=YOUR_AUTH_CODE" -d "client_id={API_KEY}" -d "client_secret={API_SECRET}" \
-d "redirect_uri={REDIRECT_URI}" -d "grant_type=authorization_code"</pre>
    <h1>Step 3: Set Access Token</h1><p>Copy the 'access_token' from the response, set it as <code>UPSTOX_ACCESS_TOKEN</code> in your <code>.env</code> file, and restart the app.</p>
    </body></html>"""

@app.route("/")
def index():
    """Renders the dashboard or guides user to login."""
    if not api_client:
        return """<h1>Welcome to the Live OI Tracker</h1>
        <p>The app isn't connected to Upstox because <code>UPSTOX_ACCESS_TOKEN</code> is missing or invalid.</p>
        <p>Ensure your API credentials are in the <code>.env</code> file, then <a href="/login">click here to log in</a>.</p>"""
    return render_template("index.html")

@app.route("/data")
def data_endpoint():
    """Provides the latest OI data to the frontend."""
    if cache["data"] is None:
        return jsonify({"error": "Data is not available yet. Please wait for the 60-second update cycle."}), 503
    return jsonify(cache["data"])

@app.route("/callback")
def callback():
    """Handles the OAuth2 callback and displays the auth code."""
    auth_code = request.args.get('code')
    return f"""<h1>Authorization Code Received</h1>
    <p>Your authorization code is: <strong>{auth_code}</strong></p>
    <p>Now use this code in the cURL command on the /login page to get your access token.</p>"""

# ==============================================================================
# --- Main Execution ---
# ==============================================================================

if __name__ == "__main__":
    if not initialize_api_client():
        logging.warning("Could not initialize API client. This is expected if UPSTOX_ACCESS_TOKEN is not set.")
        logging.warning("Running server to allow user to access /login page to get the token.")
    else:
        logging.info("API client initialized. Starting background data scheduler.")
        # Run the first update immediately in the foreground to populate initial data
        update_oi_data()
        scheduler_thread = threading.Thread(target=background_scheduler, daemon=True)
        scheduler_thread.start()

    app.run(host='0.0.0.0', port=5000, debug=False)