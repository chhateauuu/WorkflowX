import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai

openai.api_key = os.getenv("OPENAI_API_KEY")

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import dateparser
import datetime
import pytz
from dateutil import parser as dateutil_parser
import re

from server.gmail.gmail_integration import send_gmail, get_latest_emails
from server.slack_integration import send_slack_message, get_latest_slack_messages



load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

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
    Attempts to parse a date/time from user_text using dateutil's parser and special handling for relative dates.
    Also extracts meeting duration if specified (e.g., "for 2 hours").
    Returns start and end times in RFC3339 (ISO8601) format, or (None, None) if parsing fails.
    """
    
    local_tz = pytz.timezone("America/Indiana/Indianapolis")
    now_local = datetime.datetime.now(local_tz)
    
    # Special handling for common relative date terms
    tomorrow_pattern = re.compile(r'\b(tomorrow|tmr|tmrw)\b', re.IGNORECASE)
    next_week_pattern = re.compile(r'\b(next\s+week)\b', re.IGNORECASE)
    
    # Handle "tomorrow" explicitly
    tomorrow_match = tomorrow_pattern.search(user_text)
    next_week_match = next_week_pattern.search(user_text)
    
    # Pre-process the text for special cases before sending to dateutil
    modified_text = user_text
    
    try:
        # Check for duration specification in the user text
        duration_hours = 1  # Default duration is 1 hour
        
        # Common patterns for duration - simplified for reliability
        duration_patterns = [
            r'for (\d+) hours?',
            r'for (\d+)h',
            r'(\d+) hours? long',
            r'(\d+) hour meeting'
        ]
        
        for pattern in duration_patterns:
            try:
                match = re.search(pattern, user_text.lower())
                if match:
                    try:
                        duration_hours = int(match.group(1))
                        print(f"DEBUG: Found duration specification: {duration_hours} hours")
                        # Remove the duration part from the user_text to avoid confusion in date parsing
                        modified_text = re.sub(pattern, '', modified_text)
                        break
                    except (ValueError, IndexError) as e:
                        print(f"Error extracting duration: {e}")
            except Exception as e:
                print(f"Error in duration pattern matching: {e}")

        # We'll try to parse the entire user_text in fuzzy mode,
        # so it can skip unknown words or partial matches.
        dt = dateutil_parser.parse(modified_text, fuzzy=True)
        print(f"DEBUG (dateutil): user_text={modified_text}, dt={dt}")

        if dt.tzinfo is None:
            # localize if naive
            dt_local = local_tz.localize(dt)
        else:
            # convert to local tz if already has tzinfo
            dt_local = dt.astimezone(local_tz)
            
        # Handle specific date cases that might not be parsed correctly
        if tomorrow_match:
            # If "tomorrow" is in the text, ensure the date is tomorrow regardless of what dateutil parsed
            tomorrow_date = now_local.date() + datetime.timedelta(days=1)
            dt_local = dt_local.replace(year=tomorrow_date.year, month=tomorrow_date.month, day=tomorrow_date.day)
            print(f"DEBUG: Explicitly set date to tomorrow: {dt_local}")
            
        if next_week_match:
            # If "next week" is in the text, ensure the date is 7 days from now
            next_week_date = now_local.date() + datetime.timedelta(days=7)
            dt_local = dt_local.replace(year=next_week_date.year, month=next_week_date.month, day=next_week_date.day)
            print(f"DEBUG: Explicitly set date to next week: {dt_local}")

        # Create an event with the specified duration
        end_dt_local = dt_local + datetime.timedelta(hours=duration_hours)

        # Make sure we're not scheduling in the past
        if dt_local < now_local:
            # If time is in the past, assume the user meant the next occurrence
            print("Detected past time, adjusting to future")
            if dt_local.date() == now_local.date():
                # Same day but earlier time - add a day
                dt_local = dt_local + datetime.timedelta(days=1)
                print(f"Time was today but in the past, adjusted to tomorrow: {dt_local}")
            else:
                # Date in the past - add a year
                dt_local = dt_local.replace(year=now_local.year + 1)
                print(f"Date was in the past, adjusted to next year: {dt_local}")
            
            # Recalculate end time
            end_dt_local = dt_local + datetime.timedelta(hours=duration_hours)

        start_str = dt_local.isoformat()
        end_str = end_dt_local.isoformat()

        return start_str, end_str

    except Exception as e:
        # If parsing fails entirely
        print(f"DEBUG (dateutil) parse error: {e}")
        return None, None


def extract_email_and_message(user_text: str):
    """
    Attempts to extract an email address from user_text using a simple regex.
    Returns (email, user_instructions).
    If no email found, default to a placeholder.
    Also removes the email part from the user_text so we can pass leftover instructions to GPT.
    """
    email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(email_regex, user_text)
    
    if match:
        email = match.group(0)
        # Remove the email from user_text
        leftover = user_text.replace(email, "")
        leftover = leftover.replace("send email to", "")  # optional removal
        leftover = leftover.strip()
    else:
        email = "someone@example.com"
        leftover = user_text.replace("send email", "").strip()
    
    return email, leftover

def generate_email_content(instructions: str):
    """
    Takes leftover instructions (like 'telling her I can’t attend the meeting tomorrow...')
    and uses GPT to produce a subject and body.
    """
    # 1) GPT for subject
    subject_prompt = (
        "Create a concise yet clear email subject line, based on these instructions: "
        f"'{instructions}'. "
        "Return ONLY the subject line text, no quotes."
    )
    subject_resp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an AI specialized in writing short, professional email subjects."},
            {"role": "user", "content": subject_prompt},
        ],
        max_tokens=50,
        temperature=0.7,
    )
    subject = subject_resp.choices[0].message.content.strip()

    # 2) GPT for body
    body_prompt = (
        "Write a concise, polite, professional email body text based on these instructions: "
        f"'{instructions}'. "
        "Keep it fairly short, but informative."
    )
    body_resp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an AI specialized in writing polite, professional email bodies."},
            {"role": "user", "content": body_prompt},
        ],
        max_tokens=200,
        temperature=0.7,
    )
    body = body_resp.choices[0].message.content.strip()

    return subject, body



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
    classification_resp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a classifier. Classify the user's message into "
                    "one of these intents: schedule_meeting, send_email, retrieve_data, retrieve_email, send_slack, retrieve_slack or general. "
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
        # 1) Extract the email & leftover instructions from user_text
        to_email, leftover_instructions = extract_email_and_message(user_text)
    
        # 2) Pass leftover_instructions to GPT to get subject/body
        subject, body = generate_email_content(leftover_instructions)
    
        # 3) Send
        result = send_gmail(to_email, subject, body)
    
        if result:
            return {"reply": f"Email sent to {to_email} with subject: '{subject}'."}
        else:
            return {"reply": f"Failed to send email to {to_email}."}
        
    # We'll interpret "send_slack" or "slack_send" as an intent to send a message
    # And "slack_retrieve" or "retrieve_slack" as an intent to read messages

    elif "send_slack" in classification_text or "slack_send" in classification_text:
        # naive parse: "send slack message to #general hey everyone"
        # or you can do a nicer approach with GPT parsing
        channel = "#general"
        # for example, find channel name:
        if "to #random" in user_text:
            channel = "#random"
        
        # find text after "saying" or "message" ...
        # or do a quick approach
        
        match = re.search(r"(?:message|saying|say|send slack).* to (#[\w-]+).* (saying|that|:)\s*(.*)", user_text)
        if match:
            channel = match.group(1)
            text = match.group(3)
        else:
            # fallback text
            text = "Hello from WorkflowX Bot!"
        
        success = send_slack_message(channel, text)
        if success:
            return {"reply": f"Slack message sent to {channel}: '{text}'"}
        else:
            return {"reply": f"Failed to send Slack message to {channel}."}

    elif "retrieve_slack" in classification_text or "slack_retrieve" in classification_text:
        # retrieve messages from #general
        channel = "#general"
        messages = get_latest_slack_messages(channel)
        # Format them for display
        reply_str = "Latest messages:\n"
        for msg in messages:
            user = msg.get("user", "unknown")
            text = msg.get("text", "")
            reply_str += f" - {user}: {text}\n"
        
        return {"reply": reply_str}
    
    elif "retrieve_email" in classification_text:
        emails_summary = get_latest_emails(5)

        if not emails_summary:
            return {"reply": "No emails found or an error occurred."}

        return {"reply": emails_summary}





    else:
        # 'general' => normal GPT conversation
        final_resp = openai.chat.completions.create(
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
