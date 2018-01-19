import os
import flask
import requests
import json

import googleapiclient.discovery
import google.oauth2.credentials
import google_auth_oauthlib.flow

import datetime
import time
from pymongo import MongoClient
from helpers import *


# This variable specifies the name of a file that contains the OAuth 2.0
# information for this application, including its client_id and client_secret.
CLIENT_SECRETS_FILE = "client_secret.json"

# This OAuth 2.0 access scope allows for full read/write access to the
# authenticated user's account and requires requests to use an SSL connection.
SCOPES = ['https://www.googleapis.com/auth/calendar',
  'profile']
API_SERVICE_NAME = 'calendar'
API_VERSION = 'v3'

# UTC offset for local time zone
OFFSET = time.strftime('%z')
OFFSET = OFFSET[:3] + ":" + OFFSET[3:]

# configure app
app = flask.Flask(__name__)
app.secret_key = '\\xac\\xe4\\x1d\\xd6\\xaf\\xdc\\xd1\\xc9\\x91G\\x14\\x9c\\x8f\\xefv\\xf2\\x84\\xd1Zq\\xad\\xd2\\\\!'
app.static_folder = 'static'

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure oauth2 to work without https locally
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Create connection to db
# TODO: implement a users collection to store credentials outside of flask
client = MongoClient()
db = client.taskmaster

"""
IMPORTANT

If there is an invalid grant error, we must re-authorize the user throught the
authorization page.
"""

# Index page
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

# This and following methods create the login/Google authorization flow
@app.route('/login', methods=["GET", "POST"])
def login():
  if flask.request.method == "POST":

    if 'credentials' not in flask.session:
      return flask.redirect(flask.url_for('authorize'))

    return flask.redirect(flask.url_for('index'))

  else:
    return flask.render_template("login.html")

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

  # Load credentials from the session.
  myCredentials = google.oauth2.credentials.Credentials(
    **flask.session['credentials'])

  # Build Google People service and get user info
  service = googleapiclient.discovery.build('people', 'v1', credentials=myCredentials)
  profile = service.people().get(
    resourceName='people/me', personFields='names,emailAddresses').execute()
  name = profile['names'][0]['displayName']
  email = profile['emailAddresses'][0]['value']

  # Keep track of user email
  flask.session['email'] = email

  # Check if user already exists in db
  cursor = db.users.find({"email": email})
  if cursor.count() == 0:
    # Insert user into mongodb if user does not already exist in db
    # Default wakeup/sleep time and free hours
    # TODO: Inform user these are default values
    result = db.users.insert_one(
        {
          "credentials": credentials_to_dict(credentials),
          "email": email,
          "name": name,
          "wakeUp": "07:00",
          "sleep": "22:00",
          "free": "4"
        }
      )

  return flask.redirect(flask.url_for('index'))

# Define parameters for insertion into GCal
@app.route('/create', methods=["GET", "POST"])
@login_required
def create():
  if flask.request.method == "POST":
    # check if description was provided
    if not flask.request.form.get("description"):
      description = ""
    else:
      description = flask.request.form.get("description")

    # Get form items and create temporary event item
    event = {
      'summary': flask.request.form.get("eventSummary"),
      'description': description,
      'dueDate': flask.request.form.get("dueDate"),
      'duration': flask.request.form.get("duration")
    }
    print(event)
    # Load credentials from the session.
    credentials = google.oauth2.credentials.Credentials(
      **flask.session['credentials'])

    # Build the calendar service object
    calendar = googleapiclient.discovery.build(
      API_SERVICE_NAME, API_VERSION, credentials=credentials)

    # Get user's preferences
    preferences = db.users.find({"email": flask.session['email']})

    # get all events until due date
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    eventsResult = calendar.events().list(
      calendarId='primary', timeMin=now, timeMax=event['dueDate'] + ':00' + OFFSET,
      singleEvents=True, orderBy='startTime').execute()
    events = eventsResult.get('items', [])
    print(events)

    # get titles of previous events that we have sorted (cursor object)
    sorted_events = db.events.find()

    # Sort event into GCal
    print(sort(event, sorted_events, events, preferences))

    return flask.redirect(flask.url_for("index"))

  else:
    return flask.render_template("create.html")

# (User Settings)
@app.route('/preferences', methods=["GET", "POST"])
@login_required
def preferences():
  if flask.request.method == "POST":
    # Get form info
    name = flask.request.form.get("name")
    wakeUp = flask.request.form.get("wakeUp")
    sleep = flask.request.form.get("sleep")
    free = flask.request.form.get("free")

    # Update db user info
    result = db.users.update_one({"email": flask.session['email']},
      {
        "$set": {
          "name": name,
          "wakeUp": wakeUp,
          "sleep": sleep,
          "free": free
        }
      }
    )

    return flask.render_template("preferences.html", name=name, wakeUp=wakeUp,
      sleep=sleep, free=free)

  else:
    # Query db for user info
    cursor = db.users.find({"email": flask.session['email']})
    name = cursor[0]['name']
    wakeUp = cursor[0]['wakeUp']
    sleep = cursor[0]['sleep']
    free = cursor[0]['free']

    return flask.render_template("preferences.html", name=name, wakeUp=wakeUp,
      sleep=sleep, free=free)

# Logout
@app.route('/logout')
@login_required
def logout():
  flask.session.clear()
  return flask.redirect(flask.url_for('login'))

# Methods to update to newest css and js static file links
@app.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)

def dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(app.root_path,
                                     endpoint, filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)

# Handle the google Invalid Grant error
@app.errorhandler(google.auth.exceptions.RefreshError)
def handle_invalid_grant(error):
  return flask.redirect(flask.url_for('authorize'))


# sort: takes in event to sort, sorted events, all events until dueDate, and user preferences
# event: dict, sorted_events: cursor objects, events: list, preference: list
# first implementation: insert event into first free space before dueDate
def sort(event, sorted_events, events, preferences):
  # get free/busy data from now (round up to nearest 10 mins) until dueDate
  data = {
    "timeMin": roundup10(datetime.datetime.utcnow()).isoformat() + 'Z',
    "timeMax": event['dueDate'] + ':00' + OFFSET,
    "timeZone": "America/Los_Angeles",
    "items": [
      {
        "id": flask.session['email']
      }
    ]
  }
  headers = {
    'Authorization': 'Bearer %s' % flask.session['credentials']['token'],
    'Accept': 'application/json',
    'Content-Type': 'application/json ; charset=UTF-8'
  }
  r = requests.post('https://www.googleapis.com/calendar/v3/freeBusy', data=json.dumps(data),
    headers=headers)
  freeBusy = json.loads(r.text)['calendars'][flask.session['email']]['busy']

  return freeBusy


# # Create start and end datetime objects
# start, end = convert_start_end_duration(dueDate, "06:00:00", duration)

# # Create GCal event item
# event = {
#   'summary': summary,
#   'description': description,
#   'start': {
#     'dateTime': start,
#     'timeZone': 'America/Los_Angeles'
#   },
#   'end': {
#     'dateTime': end,
#     'timeZone': 'America/Los_Angeles'
#   }
# }

# Insert record of new sorting into db
# result = db.events.insert_one(
#   {
#     id
#     title
#     dueDate
#     duration
#     etc.
#   }
# )


