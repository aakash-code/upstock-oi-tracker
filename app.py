from flask import Flask, render_template, request, redirect, url_for, session
import upstox_client

app = Flask(__name__)
app.secret_key = 'your_very_secret_key'  # In a real app, use a more secure key and load it from config
REDIRECT_URI = "http://127.0.0.1:5000/callback" # The callback URL for the Flask app

@app.route('/')
def index():
    """Renders the home page with the credential input form."""
    return render_template('index.html')

@app.route('/token_login', methods=['POST'])
def token_login():
    """Handles the access token form submission."""
    session['access_token'] = request.form['access_token']
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['POST'])
def login():
    """Handles the API credentials form submission and redirects to Upstox."""
    session['api_key'] = request.form['api_key']
    session['api_secret'] = request.form['api_secret']

    api_instance = upstox_client.LoginApi()
    # Note: The state parameter is optional and can be used for security purposes
    response = api_instance.authorize(session['api_key'], REDIRECT_URI, "v2")

    # Redirect the user to the Upstox login page
    return redirect(response)

@app.route('/callback')
def callback():
    """Handles the callback from Upstox and gets the access token."""
    api_instance = upstox_client.LoginApi()
    code = request.args.get('code')

    try:
        response = api_instance.token(
            api_version="v2",
            code=code,
            client_id=session['api_key'],
            client_secret=session['api_secret'],
            redirect_uri=REDIRECT_URI,
            grant_type='authorization_code'
        )
        session['access_token'] = response.access_token
        return redirect(url_for('dashboard'))
    except upstox_client.rest.ApiException as e:
        return f"<h1>Error</h1><p>Could not retrieve access token. Please try logging in again.</p><p>Details: {e}</p>"

import tracker_logic

@app.route('/dashboard')
def dashboard():
    """Displays the main dashboard with OI data. Requires login."""
    if 'access_token' not in session:
        return redirect(url_for('index'))

    access_token = session['access_token']

    # Fetch the OI data using the logic from our tracker_logic file
    call_data, put_data = tracker_logic.get_oi_data(access_token)

    # Render the dashboard template with the fetched data
    return render_template('dashboard.html', call_data=call_data, put_data=put_data)

@app.route('/logout')
def logout():
    """Logs the user out by clearing the session."""
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Note: For production, use a proper web server like Gunicorn or uWSGI
    app.run(host='0.0.0.0', port=5000, debug=True)