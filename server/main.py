import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import dateparser
import datetime
import pytz
from dateutil import parser as dateutil_parser


load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Model for request
class ChatRequest(BaseModel):
    message: str

@app.get("/")
def root():
    return {"message": "Hello from WorkflowX API!"}

def schedule_google_event(title: str, start_datetime: str, end_datetime: str) -> str:
    creds = Credentials.from_service_account_file(
        "service_account.json",  
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    service = build("calendar", "v3", credentials=creds)
    event_body = {
        "summary": title,
        "start": {
            "dateTime": start_datetime,
            "timeZone": "America/Chicago"
        },
        "end": {
            "dateTime": end_datetime,
            "timeZone": "America/Chicago"
        },
    }
    created_event = service.events().insert(
        calendarId="abchhatkuli@gmail.com",
        body=event_body
    ).execute()
    return created_event.get("htmlLink", "No link found")


def parse_event_time(user_text: str):
    """
    Attempts to parse a date/time from user_text using dateutil's parser.
    Returns start and end times in RFC3339 (ISO8601) format, or (None, None) if parsing fails.
    """
    local_tz = pytz.timezone("America/Chicago")
    now_local = datetime.datetime.now(local_tz)

    # We'll try to parse the entire user_text in fuzzy mode,
    # so it can skip unknown words or partial matches.
    try:
        dt = dateutil_parser.parse(user_text, fuzzy=True)
        print(f"DEBUG (dateutil): user_text={user_text}, dt={dt}")

        if dt.tzinfo is None:
            # localize if naive
            dt_local = local_tz.localize(dt)
        else:
            # convert to local tz if already has tzinfo
            dt_local = dt.astimezone(local_tz)

        # We'll create a 1-hour event
        end_dt_local = dt_local + datetime.timedelta(hours=1)

        start_str = dt_local.isoformat()
        end_str = end_dt_local.isoformat()

        return start_str, end_str

    except Exception as e:
        # If parsing fails entirely
        print(f"DEBUG (dateutil) parse error: {e}")
        return None, None



@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    user_text = req.message.lower()

    # Quick hack: if user says "test calendar", skip classification & parse
    if "test calendar" in user_text:
        # Hard-code a date/time to tomorrow 2 PM (1-hour event)
        local_tz = pytz.timezone("America/Chicago")
        now_local = datetime.datetime.now(local_tz)
        # "Tomorrow" at 2 PM
        tomorrow_2pm_local = (now_local + datetime.timedelta(days=3)).replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        # End time (1 hour later)
        end_local = tomorrow_2pm_local + datetime.timedelta(hours=1)

        start_str = tomorrow_2pm_local.isoformat()
        end_str = end_local.isoformat()

        event_link = schedule_google_event(
            title="Test Calendar Event",
            start_datetime=start_str,
            end_datetime=end_str
        )
        return {"reply": f"Test event scheduled! Event link: {event_link}"}

    # Otherwise, do your normal GPT classification or fallback
    classification_resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a classifier. Classify the user's message into "
                    "one of these intents: schedule_meeting, send_email, retrieve_data, or general. "
                    "Output ONLY the intent name."
                )
            },
            {"role": "user", "content": user_text}
        ],
        max_tokens=5,
        temperature=0.0,
    )

    classification_text = classification_resp.choices[0].message.content.strip().lower()

    if "schedule_meeting" in classification_text:
        start_dt, end_dt = parse_event_time(user_text)
        if not start_dt:
            return {
                "reply": (
                    "Sorry, I couldn't understand the date/time. Try e.g. "
                    "'Schedule meeting on March 10 at 2 PM'."
                )
            }
        event_link = schedule_google_event(
            "Meeting scheduled by WorkflowX", start_dt, end_dt
        )
        return {"reply": f"Meeting scheduled! Event link: {event_link}"}

    elif "send_email" in classification_text:
        return {"reply": "Intent: send_email. [Placeholder email logic]"}

    elif "retrieve_data" in classification_text:
        return {"reply": "Intent: retrieve_data. [Placeholder data retrieval logic]"}

    else:
        # 'general' => normal GPT conversation
        final_resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant for WorkflowX.",
                },
                {"role": "user", "content": user_text},
            ],
            max_tokens=100,
            temperature=0.7,
        )
        ai_text = final_resp.choices[0].message.content.strip()
        return {"reply": ai_text}
