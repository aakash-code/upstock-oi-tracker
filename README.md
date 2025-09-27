# Upstox OI Tracker Web Application

This application provides a powerful, dynamic, and live web-based interface to track Open Interest (OI) changes for options contracts using the Upstox API.

## Features

- **Dynamic Instrument Selection:** The application automatically fetches and displays a comprehensive list of all tradable instruments (indices and stocks) that have derivatives. A live search filter makes it easy to find any instrument.
- **Dynamic Expiry Date Selection:** The expiry date dropdown is dynamically populated with all valid expiry dates for the selected instrument.
- **Live OI Dashboard:** The dashboard auto-refreshes every 60 seconds, providing a real-time view of the market.
- **Expanded Data View:** Tracks 7 strikes (ATM ± 3) and calculates OI changes over 5 different time intervals (3, 5, 10, 15, and 30 minutes).
- **Flexible Login:** Supports two login methods:
    1.  **Standard OAuth2 Flow:** Enter your API Key and Secret to go through the secure login process.
    2.  **Direct Access Token:** If you already have a valid access token, you can paste it in to go directly to the dashboard.
- **Color-Coded Tables:** Separate tables for Call and Put options, with color-coding to highlight significant OI changes.

## Prerequisites

- Python 3.7+
- An active Upstox account.
- An app created on the [Upstox Developer Console](https://upstox.com/developer/apps) to get your API Key and API Secret.

## Setup and Installation

### 1. Configure Your Upstox App's Redirect URI

This is the most important setup step. For the login process to work, you must configure the **Redirect URI** in your Upstox app settings.

- Go to your app settings on the Upstox Developer Console.
- Set the Redirect URI to: `http://127.0.0.1:5000/callback`
- Make sure to save the changes.

*(Note: If you are running this in a cloud environment like GitHub Codespaces, you must use the publicly forwarded URL provided by that environment instead of `127.0.0.1:5000`)*

### 2. Clone the Repository

Clone this repository to your local machine.

### 3. Set up a Virtual Environment

It is highly recommended to use a virtual environment to manage the project's dependencies.

```bash
# Navigate to the project directory
cd path/to/your/project

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
# On macOS and Linux:
source venv/bin/activate
# On Windows:
# venv\\Scripts\\activate
```

### 4. Install Dependencies

Install the required Python libraries using the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

## How to Run the Application

1.  **Activate your virtual environment** if you haven't already.
2.  **Run the Flask web server:**

    ```bash
    python app.py
    ```
3.  **Open your web browser** and navigate to:

    `http://127.0.0.1:5000`

4.  You will see the login page with two options. Use either your API credentials or a direct access token to log in.
5.  If using credentials, you will be redirected to the Upstox website to log in and grant access.
6.  After a successful login, you will be redirected to the application's powerful, live dashboard. Enjoy!