# Upstox OI Tracker Web Application

This application provides a web-based interface to track Open Interest (OI) changes for Nifty 50 options contracts using the Upstox API.

## Features

- **Web-based Interface:** A user-friendly web page to securely enter your Upstox API credentials.
- **Secure Authentication:** Implements the standard OAuth2 flow to authenticate with the Upstox API.
- **OI Dashboard:** Displays OI changes for At-The-Money (ATM), 2 In-The-Money (ITM), and 2 Out-of-The-Money (OTM) strikes.
- **Color-Coded Tables:** Separate tables for Call and Put options, with color-coding to highlight significant OI changes.

## Prerequisites

- Python 3.7+
- An active Upstox account.
- An app created on the [Upstox Developer Console](https://upstox.com/developer/apps) to get your API Key and API Secret.

## Setup and Installation

### 1. Configure Your Upstox App

Before you run the application, you need to configure the **Redirect URI** in your Upstox app settings.

- Go to your app settings on the Upstox Developer Console.
- Set the Redirect URI to: `http://127.0.0.1:5000/callback`
- Make sure to save the changes. This step is crucial for the login process to work.

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

4.  You will see the login page. **Enter your API Key and API Secret** and click "Login with Upstox".
5.  You will be redirected to the Upstox website to log in and grant access.
6.  After a successful login, you will be redirected back to the application's dashboard, where you will see the OI data.

## Important Notes

- Your API credentials are not stored in the application. They are used only for the initial authentication flow.
- The application uses a Flask session to securely store your `access_token` for the duration of your session.
- For simplicity, the options expiry date is hardcoded in `tracker_logic.py`. You can modify this as needed.