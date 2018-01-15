from flask import redirect, render_template, request, session, url_for
from functools import wraps
import datetime
import requests

# self-explanatory
def credentials_to_dict(credentials):
  return {'token': credentials.token,
          'refresh_token': credentials.refresh_token,
          'token_uri': credentials.token_uri,
          'client_id': credentials.client_id,
          'client_secret': credentials.client_secret,
          'scopes': credentials.scopes}

# Login required decorator
def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.11/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("credentials") is None:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Convert user input for insertion into GCal
# TEMPORARY UNTIL SORTING ALGORITHM IMPLEMENTATION
def convert_start_end_duration(date, startTime, duration):
  start_date = datetime.datetime.strptime(
      date + " " + startTime, "%Y-%m-%d %H:%M:%S")
  end_date = start_date + datetime.timedelta(hours=int(duration))
  start = str(start_date)
  end = str(end_date)
  start = start[:10] + "T" + start[11:]
  end = end[:10] + "T" + end[11:]
  return start, end
