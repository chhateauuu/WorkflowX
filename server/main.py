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
from server.hubspot_integration import get_hubspot_contacts
from server.refined_nlp import bert_classify
from server.nlp_datetime_cleaner import ai_clean_datetime, normalize_datetime_input, intelligent_date_parse





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
    Parses user text to determine meeting start and end time.
    Handles phrases like "next Wednesday at 3pm for 2 hours" or "Wednesday next week at 2pm".
    Returns (start_time, end_time) in ISO format.
    """
    local_tz = pytz.timezone("America/Chicago")
    now_local = datetime.datetime.now(local_tz)
    modified_text = user_text.lower()

    # Default duration
    duration_hours = 1

    # Extract duration if specified
    duration_patterns = [
        r"for (\d+) hours?",
        r"for (\d+)h",
        r"(\d+) hours? long",
        r"(\d+) hour meeting"
    ]
    for pattern in duration_patterns:
        match = re.search(pattern, modified_text)
        if match:
            try:
                duration_hours = int(match.group(1))
                modified_text = re.sub(pattern, '', modified_text)
                break
            except Exception as e:
                print("Duration extraction error:", e)

    # Check for next day of the week or "weekday next week" or "next week on weekday"
    weekday_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    
    # Enhanced pattern detection
    next_day_match = re.search(r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', modified_text)
    alt_form_match = re.search(r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+next\s+week', modified_text)
    next_week_day_match = re.search(r'next\s+week\s+(?:on\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', modified_text)
    next_week_at_day_match = re.search(r'next\s+week\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s+on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', modified_text)

    weekday_str = None
    if next_day_match:
        weekday_str = next_day_match.group(1).lower()
    elif alt_form_match:
        weekday_str = alt_form_match.group(1).lower()
    elif next_week_day_match:
        weekday_str = next_week_day_match.group(1).lower()
    elif next_week_at_day_match:
        weekday_str = next_week_at_day_match.group(1).lower()
    
    if weekday_str:
        target_weekday = weekday_map[weekday_str]
        current_weekday = now_local.weekday()
        
        # Calculate days to add to get to the specified weekday next week
        days_to_add = 7 - current_weekday + target_weekday
        if days_to_add >= 7:
            days_to_add = days_to_add % 7
        days_to_add += 7  # Add another week to ensure we're in "next week"
        
        dt_local = now_local + datetime.timedelta(days=days_to_add)
    else:
        dt_local = now_local

    # Try to extract time from the modified text
    time_match = re.search(r'at\s+(\d{1,2})(:(\d{2}))?\s*(am|pm)?', modified_text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(3) or 0)
        meridiem = time_match.group(4)

        if meridiem == "pm" and hour < 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

        dt_local = dt_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    else:
        # Default to 3 PM
        dt_local = dt_local.replace(hour=15, minute=0, second=0, microsecond=0)

    end_dt_local = dt_local + datetime.timedelta(hours=duration_hours)

    return dt_local.isoformat(), end_dt_local.isoformat()



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
    Takes leftover instructions (like 'telling her I can't attend the meeting tomorrow...')
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

    # # Otherwise, do your normal GPT classification or fallback
    # classification_resp = openai.chat.completions.create(
    #     model="gpt-3.5-turbo",
    #     messages=[
    #         {
    #             "role": "system",
    #             "content": (
    #                 "You are a classifier. Classify the user's message into "
    #                 "one of these intents: schedule_meeting, send_email, retrieve_data, retrieve_email, send_slack, retrieve_slack, retrieve_crm or general. "
    #                 "Output ONLY the intent name."
    #             )
    #         },
    #         {"role": "user", "content": user_text}
    #     ],
    #     max_tokens=5,
    #     temperature=0.0,
    # )

    # classification_text = classification_resp.choices[0].message.content.strip().lower()

    classification_text = bert_classify(user_text)
    print("💡 NLP Classification:", classification_text)


    if "schedule_meeting" in classification_text:
        # First normalize the input to handle common typos and restructure date/time expressions
        user_text = normalize_datetime_input(user_text)
        print(f"Normalized text: {user_text}")
        
        # Try advanced intelligent date parsing first
        start_dt_obj, end_dt_obj = intelligent_date_parse(user_text)
        
        if start_dt_obj and end_dt_obj:
            # Convert to ISO format strings
            start_dt = start_dt_obj.isoformat()
            end_dt = end_dt_obj.isoformat()
            print(f"Intelligent parser result: start={start_dt}, end={end_dt}")
        else:
            # If intelligent parsing failed, try AI-based cleaner
            ai_response = ai_clean_datetime(user_text)
            print(f"AI response: {ai_response}")

            # Try to parse the structured format from AI
            match = re.search(r"START=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\s+END=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})", ai_response)
            if match:
                start_dt = match.group(1)
                end_dt = match.group(2)
                print(f"AI parsed: start={start_dt}, end={end_dt}")
            else:
                # If AI cleaner failed, fallback to manual parser
                print("AI parser failed, using manual parser")
                start_dt, end_dt = parse_event_time(user_text)

        # Still failed? Bail out
        if not start_dt:
            return {
                "reply": (
                    "Sorry, I couldn't understand the date/time. Try rephrasing it like: "
                    "'Schedule meeting on March 10 at 2 PM for 2 hours'."
                )
            }
            
        # Calculate duration from start and end times
        start_time = dateutil_parser.parse(start_dt)
        end_time = dateutil_parser.parse(end_dt)
        duration_hours = (end_time - start_time).total_seconds() / 3600
        
        # Create a more descriptive meeting title based on the original request
        meeting_title = f"Meeting: {user_text.strip()[:50]}"
        
        event_link = schedule_google_event(
            meeting_title, 
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
    
    elif "retrieve_crm" in classification_text or "hubspot_retrieve" in classification_text:
        contacts = get_hubspot_contacts(limit=5)
        if not contacts:
            return {"reply": "No HubSpot contacts found or an error occurred."}

        reply_str = "📇 Here are your top 5 HubSpot contacts:\n"
        for i, c in enumerate(contacts, start=1):
            reply_str += (
                f"\n{i}) 🧑 {c['firstname']} {c['lastname']}\n"
                f"    📧 {c['email']}\n"
                f"    🆔 ID: {c['id']}\n"
            )
        return {"reply": reply_str}






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
