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
    Also extracts meeting duration if specified (e.g., "for 2 hours").
    Returns start and end times in RFC3339 (ISO8601) format, or (None, None) if parsing fails.
    """
    local_tz = pytz.timezone("America/Indiana/Indianapolis")
    now_local = datetime.datetime.now(local_tz)

    # Check for duration specification in the user text
    duration_hours = 1  # Default duration is 1 hour
    
    # Common patterns for duration
    duration_patterns = [
        r'for (\d+) hours?',
        r'for (\d+)h',
        r'(\d+) hours? (long|duration)',
        r'(\d+) hour (meeting|call)',
        r'duration of (\d+) hours?',
        r'lasting (\d+) hours?'
    ]
    
    import re
    for pattern in duration_patterns:
        match = re.search(pattern, user_text.lower())
        if match:
            try:
                duration_hours = int(match.group(1))
                print(f"DEBUG: Found duration specification: {duration_hours} hours")
                # Remove the duration part from the user_text to avoid confusion in date parsing
                user_text = re.sub(pattern, '', user_text)
                break
            except (ValueError, IndexError):
                pass

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

        # Create an event with the specified duration
        end_dt_local = dt_local + datetime.timedelta(hours=duration_hours)

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
        # Check for duration in test calendar command
        duration_hours = 1  # Default duration
        duration_match = None
        
        # Look for patterns like "test calendar for 2 hours"
        duration_patterns = [
            r'for (\d+) hours?',
            r'for (\d+)h',
            r'(\d+) hours',
        ]
        
        import re
        for pattern in duration_patterns:
            match = re.search(pattern, user_text.lower())
            if match:
                try:
                    duration_hours = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    pass
                
        # Hard-code a date/time to tomorrow 2 PM (with specified duration)
        local_tz = pytz.timezone("America/Chicago")
        now_local = datetime.datetime.now(local_tz)
        # "Tomorrow" at 2 PM
        tomorrow_2pm_local = (now_local + datetime.timedelta(days=3)).replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        # End time (with specified duration)
        end_local = tomorrow_2pm_local + datetime.timedelta(hours=duration_hours)

        start_str = tomorrow_2pm_local.isoformat()
        end_str = end_local.isoformat()

        event_link = schedule_google_event(
            title=f"Test Calendar Event ({duration_hours} hour{'s' if duration_hours != 1 else ''})",
            start_datetime=start_str,
            end_datetime=end_str
        )
        return {"reply": f"Test event scheduled for {duration_hours} hour{'s' if duration_hours != 1 else ''}! Event link: {event_link}"}

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
                    "'Schedule meeting on March 10 at 2 PM for 2 hours'."
                )
            }
        
        # Calculate duration from start and end times
        start_time = dateutil_parser.parse(start_dt)
        end_time = dateutil_parser.parse(end_dt)
        duration_hours = (end_time - start_time).total_seconds() / 3600
        
        event_link = schedule_google_event(
            f"Meeting scheduled by WorkflowX ({int(duration_hours)} hour{'s' if duration_hours != 1 else ''})", 
            start_dt, 
            end_dt
        )
        
        # Format start time more nicely for the response
        start_time_local = start_time.strftime("%A, %B %d at %I:%M %p")
        
        return {
            "reply": f"Meeting scheduled for {start_time_local} with a duration of {int(duration_hours)} hour{'s' if duration_hours != 1 else ''}! Event link: {event_link}"
        }

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
