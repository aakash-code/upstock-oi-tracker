# Professional OI Tracker - A Database-Driven Web Application

This is a professional-grade, database-driven web application designed to track and analyze Open Interest (OI) changes for Futures and Options (F&O) contracts using the Upstox API. The architecture is designed for performance, reliability, and scalability.

## Key Architectural Features

- **Database-Centric Design:** The application is built around a local SQLite database that stores all instrument data, historical OI data points, and calculated results. This makes the application incredibly fast and reliable.
- **Structured Flask Application:** The project follows a professional Flask application structure, separating concerns into distinct modules for the web layer (`app.py`), database interactions (`database.py`), and core business logic (`logic.py`).
- **On-Demand Data Processing:** The application uses a robust model where the frontend requests data, and the backend fetches, calculates, and stores the results in real-time, ensuring the data is always fresh.
- **Dynamic User Interface:** The UI is fully dynamic, populating instrument lists and expiry dates directly from the local database and providing a live, auto-refreshing view of the market data.

## Features

- **Dynamic Instrument & Expiry Selection:** Automatically populates a full list of tradable F&O instruments and their valid future expiry dates from the local database.
- **Live OI Dashboard:** The dashboard auto-refreshes every 60 seconds.
- **Expanded Data View:** Tracks 7 strikes (ATM ± 3) and calculates OI changes over 5 different time intervals (3m, 5m, 10m, 15m, 30m).
- **Flexible Login:** Supports both standard OAuth2 login and direct access token login.

## Project Structure

```
/
├── app.py                  # Main Flask application file (routes and server)
├── database.py             # Handles all database setup and queries
├── download_contracts.py   # Script to download and populate the instrument database
├── logic.py                # Core business logic for fetching and calculations
├── requirements.txt        # Python dependencies
├── tracker.db              # The SQLite database file (created on setup)
└── templates/
    ├── base.html           # Base HTML template for all pages
    ├── index.html          # The login page
    └── dashboard.html      # The main OI tracker dashboard
```

## Setup and Installation

### 1. Configure Your Upstox App's Redirect URI

This is the most important setup step. For the login process to work, you must configure the **Redirect URI** in your Upstox app settings.

- Go to your app settings on the Upstox Developer Console.
- Set the Redirect URI to: `http://127.0.0.1:5000/callback`
- Make sure to save the changes.

### 2. Clone the Repository & Set Up Environment

```bash
# Clone this repository
git clone <your-repo-url>
cd <your-repo-directory>

# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up the Local Database (One-Time Setup)

This is a one-time process to initialize your local data store.

**a. Create the Database File:**
Run the `database.py` script directly. This will create the `tracker.db` file and all the necessary tables.
```bash
python database.py
```

**b. Download Contracts and Populate the Database:**
Run the `download_contracts.py` script. This will download the latest list of all F&O instruments from Upstox and save them to your local database.
```bash
python download_contracts.py
```
*(Note: It is recommended to run this script periodically, e.g., once a day, to keep your instrument list up-to-date.)*

## How to Run the Application

1.  **Activate your virtual environment.**
2.  **Run the Flask web server:**

    ```bash
    python app.py
    ```
3.  **Open your web browser** and navigate to: `http://127.0.0.1:5000`
4.  Use one of the two login methods to access the dashboard. Enjoy your fast, reliable, and powerful new OI Tracker!