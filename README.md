# Live OI Tracker Dashboard

This project is a web-based dashboard that provides a live, real-time view of Open Interest (OI) changes for NIFTY options. It is built with a Python Flask backend and a simple HTML/JavaScript frontend styled with Tailwind CSS. The application connects to the Upstox API to fetch live market data.

## Features

- **Live Data:** The dashboard auto-refreshes every 60 seconds to provide a near real-time view of the market.
- **Expanded Data View:** Tracks 7 strikes (ATM ± 3) for both Call and Put options.
- **Multiple Time Intervals:** Calculates and displays the percentage change in OI over 3, 5, 10, 15, and 30-minute intervals.
- **Color-Coded Tables:** Automatically highlights cells in red when OI changes exceed predefined thresholds, making it easy to spot significant movements.
- **Audio Alerts:** Plays a sound alert if more than 50% of the displayed cells are highlighted, ensuring you don't miss major market shifts.
- **Automatic Expiry Selection:** Intelligently detects and tracks the nearest weekly expiry date, so no manual configuration is needed.
- **Easy Setup:** Requires minimal setup with clear instructions for API credential configuration.

## Technology Stack

- **Backend:** Flask (Python)
- **Frontend:** HTML, Tailwind CSS, Vanilla JavaScript
- **API:** Upstox API
- **Dependencies:** `upstox-python-sdk`, `python-dotenv`, `gunicorn`

## Setup and Installation

Follow these steps to get the application running on your local machine.

### Prerequisites

- Python 3.8 or higher
- An active Upstox account with API access enabled.

### 1. Clone the Repository

First, clone this repository to your local machine.

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. Install Dependencies

Install all the necessary Python packages using `pip` and the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 3. Configure API Credentials

The application uses a `.env` file to manage your Upstox API credentials.

1.  **Create the file:** A `.env` file should be present in the root of the project. If not, you can create it.
2.  **Fill in your details:** Open the `.env` file and replace the placeholder values with your actual credentials.

    ```
    # Your Upstox API Key from the developer console.
    UPSTOX_API_KEY="YOUR_API_KEY"

    # Your Upstox API Secret from the developer console.
    UPSTOX_API_SECRET="YOUR_API_SECRET"

    # The access token you generate via the OAuth2 flow.
    UPSTOX_ACCESS_TOKEN="YOUR_ACCESS_TOKEN"

    # This must match the Redirect URI set in your Upstox developer app settings.
    UPSTOX_REDIRECT_URI="http://127.0.0.1:5000/callback"
    ```

#### How to get your `UPSTOX_ACCESS_TOKEN`:

The access token is temporary and needs to be generated via a login process. Follow these steps carefully.

1.  **Fill in your basic credentials** in the `.env` file: `UPSTOX_API_KEY`, `UPSTOX_API_SECRET`, and `UPSTOX_REDIRECT_URI`.

2.  **Create a `login.py` file** in the project directory and add the following code:
    ```python
    import upstox_client
    import os
    from dotenv import load_dotenv

    load_dotenv()

    API_KEY = os.environ.get("UPSTOX_API_KEY")
    API_SECRET = os.environ.get("UPSTOX_API_SECRET")
    REDIRECT_URI = os.environ.get("UPSTOX_REDIRECT_URI")

    api_instance = upstox_client.LoginApi()
    api_response = api_instance.authorise(API_KEY, "v2", REDIRECT_URI)

    print(api_response)
    ```

3.  **Run `login.py`** from your terminal to get the login URL:
    ```bash
    python login.py
    ```

4.  **Authorize and get the Auth Code**: Copy the URL printed in the terminal and paste it into your web browser. Log in with your Upstox credentials. After successful login, you will be redirected to a new URL. Copy the `code` value from this URL. It will look like this: `http://127.0.0.1:5000/callback?code=YOUR_AUTH_CODE`.

5.  **Create a `get_token.py` file** and add the following code. Paste the `AUTH_CODE` you copied in the previous step.
    ```python
    import upstox_client
    import os
    from dotenv import load_dotenv

    load_dotenv()

    API_KEY = os.environ.get("UPSTOX_API_KEY")
    API_SECRET = os.environ.get("UPSTOX_API_SECRET")
    REDIRECT_URI = os.environ.get("UPSTOX_REDIRECT_URI")
    AUTH_CODE = "PASTE_YOUR_AUTH_CODE_HERE"

    configuration = upstox_client.Configuration()
    api_instance = upstox_client.LoginApi(upstox_client.ApiClient(configuration))
    api_response = api_instance.token(
        api_version="v2",
        code=AUTH_CODE,
        client_id=API_KEY,
        client_secret=API_SECRET,
        redirect_uri=REDIRECT_URI,
        grant_type="authorization_code"
    )

    print(api_response)
    ```

6.  **Run `get_token.py`** to get your access token:
    ```bash
    python get_token.py
    ```

7.  **Set the Access Token**: Copy the `access_token` value from the output and paste it into the `UPSTOX_ACCESS_TOKEN` field in your `.env` file.

You are now ready to run the main application!

### 4. Run the Application

Once your credentials are set up, you can run the application using the following command:

```bash
python app.py
```

The server will start, and you can view the dashboard by opening your web browser and navigating to:

**http://127.0.0.1:5000**

The application will start fetching data, and the dashboard will come to life. The status of the application will be displayed at the top of the page.

---
This `README.md` provides clear instructions for setting up and running the OI Tracker dashboard. Let me know if you would like any other sections or details added.