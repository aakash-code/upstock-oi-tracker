from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import upstox_client
import database
import logic

app = Flask(__name__)
# In a real app, this key should be loaded from a secure config file
app.secret_key = 'a_very_secret_key_that_should_be_changed'

# --- Main Page Routes ---

@app.route('/')
def index():
    """Renders the login page."""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Renders the main dashboard page."""
    if 'access_token' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html')

# --- Authentication Routes ---

@app.route('/callback')
def callback():
    """Handles the OAuth callback from Upstox and gets the access token."""
    code = request.args.get('code')
    api_key = session.get('api_key')
    api_secret = session.get('api_secret')
    # The redirect URI must match exactly what is configured in the Upstox App
    redirect_uri = url_for('callback', _external=True)

    if not all([code, api_key, api_secret]):
        return "Error: Missing required session data or callback code.", 400

    try:
        api_instance = upstox_client.LoginApi()
        response = api_instance.token(
            api_version="v2",
            code=code,
            client_id=api_key,
            client_secret=api_secret,
            redirect_uri=redirect_uri,
            grant_type='authorization_code'
        )
        session['access_token'] = response.access_token
        return redirect(url_for('dashboard'))

    except upstox_client.rest.ApiException as e:
        print(f"API Exception during token exchange: {e}")
        return "Error: Could not obtain access token from Upstox.", 500

@app.route('/login', methods=['POST'])
def login():
    """Handles the API credentials login flow by redirecting to Upstox."""
    session['api_key'] = request.form.get('api_key')
    session['api_secret'] = request.form.get('api_secret')

    redirect_uri = url_for('callback', _external=True)

    api_instance = upstox_client.LoginApi()
    response = api_instance.authorize(session['api_key'], redirect_uri, "v2")

    return redirect(response)

@app.route('/token_login', methods=['POST'])
def token_login():
    """Handles direct access token login."""
    session['access_token'] = request.form.get('access_token')
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    """Logs the user out."""
    session.clear()
    return redirect(url_for('index'))

# --- Debugging Route ---

@app.route('/debug')
def debug():
    """A debugging page to show session values."""
    api_key = session.get('api_key', 'Not Set')
    # Generate the redirect_uri to show exactly what Flask is creating
    try:
        redirect_uri = url_for('callback', _external=True)
    except Exception as e:
        redirect_uri = f"Error generating URL: {e}"

    return render_template('debug.html', api_key=api_key, redirect_uri=redirect_uri)

# --- API Endpoints ---

@app.route('/api/instruments')
def api_instruments():
    """API endpoint to get the list of tradable instruments."""
    instruments = database.get_tradable_instruments()
    return jsonify({'instruments': instruments})

@app.route('/api/expiry-dates')
def api_expiry_dates():
    """API endpoint to get expiry dates for a symbol."""
    symbol = request.args.get('symbol')
    if not symbol:
        return jsonify({'error': 'Symbol parameter is required'}), 400
    dates = database.get_available_expiry_dates(symbol)
    return jsonify({'expiry_dates': dates})

@app.route('/api/data')
def api_data():
    """
    API endpoint to trigger an update and get the latest OI data.
    This is the main endpoint called by the frontend to get live data.
    """
    if 'access_token' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    symbol = request.args.get('symbol')
    expiry = request.args.get('expiry')

    if not all([symbol, expiry]):
        return jsonify({'error': 'Symbol and expiry parameters are required'}), 400

    logic.update_tracked_instruments(session['access_token'], symbol, expiry)

    latest_results = database.get_latest_oi_results(symbol, expiry)

    return jsonify(latest_results)


if __name__ == '__main__':
    # Initialize the database if it doesn't exist
    database.init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)