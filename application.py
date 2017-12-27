import os
import flask
import requests

import googleapiclient.discovery
import google.oauth2.credentials
import google_auth_oauthlib.flow

import datetime

from helpers import *


# This variable specifies the name of a file that contains the OAuth 2.0
# information for this application, including its client_id and client_secret.
CLIENT_SECRETS_FILE = "client_secret.json"

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = ['https://www.googleapis.com/auth/calendar']
API_SERVICE_NAME = 'calendar'
API_VERSION = 'v3'

app = flask.Flask(__name__)
app.secret_key = '\\xac\\xe4\\x1d\\xd6\\xaf\\xdc\\xd1\\xc9\\x91G\\x14\\x9c\\x8f\\xefv\\xf2\\x84\\xd1Zq\\xad\\xd2\\\\!'
app.static_folder = 'static'

# Configure oauth2 to work without https locally
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

"""
IMPORTANT

If there is an invalid grant error, we must re-authorize the user throught the
authorization page.
"""

@app.route('/')
@login_required
def index():
  # Load credentials from the session.
  credentials = google.oauth2.credentials.Credentials(
      **flask.session['credentials'])

  # Build the calendar service object
  calendar = googleapiclient.discovery.build(
      API_SERVICE_NAME, API_VERSION, credentials=credentials)

  # Get next 10 upcoming events
  now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
  eventsResult = calendar.events().list(
    calendarId='primary', timeMin=now, maxResults=10, singleEvents=True,
    orderBy='startTime').execute()
  events = eventsResult.get('items', [])

  # Save credentials back to session in case access token was refreshed.
  # ACTION ITEM: In a production app, you likely want to save these
  #              credentials in a persistent database instead.
  flask.session['credentials'] = credentials_to_dict(credentials)

  return flask.render_template("index.html", events=events)

@app.route('/login')
def login():
  if 'credentials' not in flask.session:
    return flask.redirect('authorize')

  return flask.redirect(flask.url_for('index'))

@app.route('/authorize')
def authorize():
  # Create flow instance to manage the OAuth 2.0 Authorization Grant Flow steps.
  flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      CLIENT_SECRETS_FILE, scopes=SCOPES)

  flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

  authorization_url, state = flow.authorization_url(
      # Enable offline access so that you can refresh an access token without
      # re-prompting the user for permission. Recommended for web server apps.
      access_type='offline',
      # Enable incremental authorization. Recommended as a best practice.
      include_granted_scopes='true')

  # Store the state so the callback can verify the auth server response.
  flask.session['state'] = state

  return flask.redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
  # Specify the state when creating the flow in the callback so that it can
  # verified in the authorization server response.
  state = flask.session['state']

  flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
      CLIENT_SECRETS_FILE, scopes=SCOPES, state=state)
  flow.redirect_uri = flask.url_for('oauth2callback', _external=True)

  # Use the authorization server's response to fetch the OAuth 2.0 tokens.
  authorization_response = flask.request.url
  flow.fetch_token(authorization_response=authorization_response)

  # Store credentials in the session.
  # ACTION ITEM: In a production app, you likely want to save these
  #              credentials in a persistent database instead.
  credentials = flow.credentials
  flask.session['credentials'] = credentials_to_dict(credentials)

  return flask.redirect(flask.url_for('login'))

@app.route('/create', methods=["GET", "POST"])
@login_required
def create():
  if flask.request.method == "POST":

    # Get form items
    summary = flask.request.form.get("eventSummary")
    dueDate = flask.request.form.get("dueDate")
    duration = flask.request.form.get("duration")
    if not flask.request.form.get("description"):
      description = ""
    else:
      description = flask.request.form.get("description")

    # Create start and end datetime objects
    start, end = convert_start_end_duration(dueDate, "06:00:00", duration)

    # Create GCal event item
    event = {
      'summary': summary,
      'description': description,
      'start': {
        'dateTime': start,
        'timeZone': 'America/Los_Angeles'
      },
      'end': {
        'dateTime': end,
        'timeZone': 'America/Los_Angeles'
      }
    }

    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
      **flask.session['credentials'])

    # Build the calendar service object
    calendar = googleapiclient.discovery.build(
      API_SERVICE_NAME, API_VERSION, credentials=credentials)

    # Insert event into GCal
    calendar.events().insert(calendarId='primary', body=event).execute()

    return flask.redirect(flask.url_for("index"))

  else:
    return flask.render_template("create.html")

@app.route('/preferences')
@login_required
def preferences():

  return flask.render_template("preferences.html")

