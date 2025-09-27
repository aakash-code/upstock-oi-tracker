import sqlite3
import urllib.request
import gzip
import json
import io

def download_and_populate_contracts():
    """
    Downloads the NFO instruments file from Upstox, parses it,
    and populates the SQLite database.
    """
    INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NFO.json.gz"
    conn = None  # Initialize conn to None

    try:
        print("Starting download of NFO instrument list...")
        with urllib.request.urlopen(INSTRUMENTS_URL) as response:
            compressed_file = io.BytesIO(response.read())
            print("Download complete. Decompressing and parsing JSON...")
            with gzip.GzipFile(fileobj=compressed_file, mode='r') as decompressed_file:
                data = json.load(decompressed_file)
        print("Parsing complete.")

        # Connect to the database
        conn = sqlite3.connect('instruments.db')
        cursor = conn.cursor()

        # Clear the table before inserting new data
        cursor.execute('DELETE FROM fno_instruments')
        print("Old data cleared from 'fno_instruments' table.")

        contracts_to_insert = []
        for row in data:
            # Prepare a tuple with the data for insertion
            contract_data = (
                row.get('instrument_key'),
                row.get('exchange'),
                row.get('tradingsymbol'),
                row.get('name'),
                row.get('underlying_key'),
                row.get('underlying_symbol'),
                row.get('instrument_type'),
                row.get('expiry'),
                row.get('strike')
            )
            contracts_to_insert.append(contract_data)

        # Use executemany for efficient bulk insertion
        cursor.executemany('''
            INSERT INTO fno_instruments (
                instrument_key, exchange, tradingsymbol, name, underlying_key,
                underlying_symbol, instrument_type, expiry, strike
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', contracts_to_insert)

        print(f"Successfully inserted {len(contracts_to_insert)} contracts into the database.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.commit()
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    download_and_populate_contracts()