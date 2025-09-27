import sqlite3

def setup_database():
    """
    Sets up the SQLite database and creates the necessary tables.
    This function should be run once to initialize the database.
    """
    try:
        # Connect to the SQLite database (this will create the file if it doesn't exist)
        conn = sqlite3.connect('instruments.db')
        cursor = conn.cursor()

        # Drop the table if it exists to ensure a clean setup
        cursor.execute('DROP TABLE IF EXISTS fno_instruments')

        # Create the table to store F&O instrument data
        # Using TEXT for most fields for simplicity, as SQLite is flexible.
        # REAL is used for strike price for numerical sorting.
        cursor.execute('''
            CREATE TABLE fno_instruments (
                instrument_key TEXT PRIMARY KEY,
                exchange TEXT,
                tradingsymbol TEXT,
                name TEXT,
                underlying_key TEXT,
                underlying_symbol TEXT,
                instrument_type TEXT,
                expiry TEXT,
                strike REAL
            )
        ''')

        print("Database 'instruments.db' created successfully.")
        print("Table 'fno_instruments' created successfully.")

        # Add an index on underlying_symbol for faster lookups
        cursor.execute('CREATE INDEX idx_underlying_symbol ON fno_instruments (underlying_symbol)')
        cursor.execute('CREATE INDEX idx_expiry ON fno_instruments (expiry)')
        print("Indexes created for faster queries.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.commit()
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    setup_database()