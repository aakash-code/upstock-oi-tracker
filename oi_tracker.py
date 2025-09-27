import upstox_client
from upstox_client.rest import ApiException
import os
import time
from datetime import datetime
import pandas as pd
from rich.console import Console
from rich.table import Table

# --- Configuration ---
# It's recommended to set these as environment variables
API_KEY = os.environ.get("UPSTOX_API_KEY", "YOUR_API_KEY")
ACCESS_TOKEN = os.environ.get("UPSTOX_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")
underlying_instrument = "NSE_INDEX|Nifty 50"
# Hardcoded expiry for simplicity. In a real application, this should be dynamic.
expiry_date = "2025-12-31"

def get_api_client():
    """Creates and returns an Upstox API client instance."""
    configuration = upstox_client.Configuration()
    configuration.access_token = ACCESS_TOKEN
    api_client = upstox_client.ApiClient(configuration)
    return api_client

def get_ltp(api_client, instrument_key):
    """Fetches the Last Traded Price (LTP) for a given instrument key."""
    api_instance = upstox_client.MarketQuoteApi(api_client)
    try:
        api_response = api_instance.ltp(instrument_key, "v2")
        # The response is a dictionary with the instrument key as the key
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
        # Ensure we don't go out of bounds
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

def create_oi_table(title, data, console):
    """Creates and displays a table for OI data with color coding."""
    table = Table(title=title)
    table.add_column("Strike Price", justify="right", style="cyan", no_wrap=True)
    table.add_column("10 mins (%)", justify="right")
    table.add_column("15 mins (%)", justify="right")
    table.add_column("30 mins (%)", justify="right")

    red_cell_count = 0
    thresholds = {10: 10, 15: 15, 30: 25}

    for strike in sorted(data.keys()):
        changes = data[strike]
        row = [f"{strike}"]
        for interval, threshold in thresholds.items():
            change = changes.get(interval, 0)
            cell_str = f"{change:.2f}"
            if change > threshold:
                cell_str = f"[bold red]{cell_str}[/bold red]"
                red_cell_count += 1
            row.append(cell_str)
        table.add_row(*row)

    console.print(table)
    return red_cell_count

def play_alert_sound(console):
    """Plays an alert sound by printing a bell character and a message."""
    console.print("\a") # ASCII Bell character
    console.print("[bold red]!!! ALERT: More than 50% of cells are color-coded !!![/bold red]")

def main():
    """Main function to run the OI tracker."""
    console = Console()
    api_client = get_api_client()

    console.print("--- Upstox OI Tracker ---")
    if "YOUR_ACCESS_TOKEN" in ACCESS_TOKEN:
        console.print("[bold red]Please set your UPSTOX_ACCESS_TOKEN environment variable.[/bold red]")
        return

    oi_data_store = {}

    while True:
        try:
            console.print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching latest data...")

            ltp = get_ltp(api_client, underlying_instrument)
            if not ltp:
                time.sleep(60)
                continue

            option_chain = get_option_chain(api_client, underlying_instrument, expiry_date)
            if not option_chain:
                time.sleep(60)
                continue

            all_strikes = sorted(list(set([strike.strike_price for strike in option_chain[0].put_options])))
            atm_strike = find_atm_strike(ltp, all_strikes)
            relevant_strikes = get_relevant_strikes(atm_strike, all_strikes)

            call_instruments = {s.strike_price: s.instrument_key for s in option_chain[0].call_options if s.strike_price in relevant_strikes}
            put_instruments = {s.strike_price: s.instrument_key for s in option_chain[0].put_options if s.strike_price in relevant_strikes}

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
                            oi_data_store[instrument_key]['data'].append((current_time, latest_oi))

            console.clear()
            total_red_cells = 0
            for option_type in ["call", "put"]:
                table_data = {}
                for key, value in oi_data_store.items():
                    if value['type'] == option_type:
                        changes = {}
                        for minutes_ago in [10, 15, 30]:
                            past_time = current_time - pd.Timedelta(minutes=minutes_ago)
                            past_data_points = [d for d in value['data'] if d[0] <= past_time]
                            if past_data_points:
                                initial_oi = past_data_points[-1][1]
                                current_oi = value['data'][-1][1]
                                changes[minutes_ago] = calculate_oi_change(initial_oi, current_oi)
                        table_data[value['strike']] = changes
                total_red_cells += create_oi_table(f"{option_type.upper()} OI Change %", table_data, console)

            total_cells = len(relevant_strikes) * 3 * 2
            if total_cells > 0 and (total_red_cells / total_cells) > 0.5:
                play_alert_sound(console)

            console.print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            time.sleep(60)

        except KeyboardInterrupt:
            console.print("\nExiting...")
            break
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
            time.sleep(60)

if __name__ == "__main__":
    main()