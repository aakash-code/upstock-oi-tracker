import sqlite3
import urllib.request
import gzip
import json
import io
import database

def populate_instruments_from_file():
    """
    Downloads the NFO instruments file from Upstox, parses it,
    and populates the SQLite database.
    """
    INSTRUMENTS_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NFO.json.gz"
    conn = None  # Initialize conn to None to prevent UnboundLocalError

    try:
        print("Starting download of NFO instrument list...")
        with urllib.request.urlopen(INSTRUMENTS_URL) as response:
            compressed_file = io.BytesIO(response.read())
            print("Download complete. Decompressing and parsing JSON...")
            with gzip.GzipFile(fileobj=compressed_file, mode='r') as decompressed_file:
                data = json.load(decompressed_file)
        print("Parsing complete.")

        conn = database.get_db_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM instruments')
        print("Old data cleared from 'instruments' table.")

        contracts_to_insert = []
        for row in data:
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

        cursor.executemany('''
            INSERT INTO instruments (
                instrument_key, exchange, tradingsymbol, name, underlying_key,
                underlying_symbol, instrument_type, expiry, strike
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', contracts_to_insert)

        print(f"Successfully inserted {len(contracts_to_insert)} contracts into the database.")

    except Exception as e:
        print(f"An error occurred during contract download: {e}")
    finally:
        if conn:
            conn.commit()
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    populate_instruments_from_file()