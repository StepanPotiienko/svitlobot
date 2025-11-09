"""Google Calendar integration helpers.

The module provides a small helper to obtain an authenticated service and create events.
It uses the installed-app OAuth flow.
"""

from typing import Dict
import pickle
from pathlib import Path


SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_service(credentials_path: str, token_path: str, scopes=None):
    """Return an authorized Google Calendar service instance.

    credentials_path: path to OAuth client secrets JSON (from Google Cloud Console)
    token_path: path where to save token (json/pickle)

    Raises RuntimeError with actionable message if google libraries are missing.
    """
    if scopes is None:
        scopes = SCOPES

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as e:
        raise RuntimeError(
            "Google client libraries are required. Install from requirements.txt"
        ) from e

    creds = None
    token_file = Path(token_path)
    if token_file.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), scopes)
        except Exception:
            # fallback to pickle
            try:
                with open(token_file, "rb") as fh:
                    creds = pickle.load(fh)
            except Exception:
                creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), scopes
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        try:
            with open(token_file, "w", encoding="utf-8") as fh:
                fh.write(creds.to_json())
        except Exception:
            try:
                with open(token_file, "wb") as fh:
                    pickle.dump(creds, fh)
            except Exception:
                # best-effort; ignore failures
                pass

    service = build("calendar", "v3", credentials=creds)
    return service


def create_event(service, calendar_id: str, event_body: Dict) -> Dict:
    """Insert an event into calendar_id and return the created event resource.

    event_body should conform to Google Calendar API event resource.
    """
    created = service.events().insert(calendarId=calendar_id, body=event_body).execute()
    return created


def list_events(
    service, calendar_id: str, time_min: str | None = None, time_max: str | None = None
):
    """Return a generator of events in the given time window.

    time_min and time_max should be RFC3339 timestamp strings (ISO with offset).
    If omitted, the API will return upcoming events according to its defaults.
    """
    page_token = None
    while True:
        req = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            showDeleted=False,
            orderBy="startTime",
            pageToken=page_token,
        )
        resp = req.execute()
        for ev in resp.get("items", []):
            yield ev
        page_token = resp.get("nextPageToken")
        if not page_token:
            break


def delete_event(service, calendar_id: str, event_id: str):
    """Delete an event by id. Returns nothing. Raises HttpError on failure."""
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
