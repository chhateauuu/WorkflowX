import os
import pickle
import pathlib
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Scopes: "gmail.send" for sending emails, "gmail.readonly" if you also want to read.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",  # if you want reading
]

def get_gmail_credentials():
    """
    Returns user OAuth credentials for accessing the Gmail API.
    1) Checks for a valid token.pickle (tokens from prior login).
    2) If missing or invalid, runs a local OAuth flow in the browser.
    3) Saves refreshed tokens to token.pickle.
    """
    creds = None
    # We'll store the token here
    token_path = pathlib.Path(__file__).parent / "gmail_token.pickle"
    # Path to your client_id credentials file
    creds_path = pathlib.Path(__file__).parent / "credentials.json"

    # 1. Check if we have an existing token
    if token_path.exists():
        with open(token_path, "rb") as token_file:
            creds = pickle.load(token_file)

    # 2. If no creds or invalid, do a new OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 3. Save the creds for next time
        with open(token_path, "wb") as token_file:
            pickle.dump(creds, token_file)

    return creds
