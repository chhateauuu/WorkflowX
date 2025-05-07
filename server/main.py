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

from gmail.gmail_integration import send_gmail, get_latest_emails
from slack_integration import send_slack_message, get_latest_slack_messages
from hubspot_integration import (
    get_hubspot_contacts,
    create_hubspot_contact,
    update_hubspot_contact
)
from refined_nlp import bert_classify
from nlp_datetime_cleaner import ai_clean_datetime, normalize_datetime_input, intelligent_date_parse, normalize_text

from auth import router as auth_router
from database import init_db

app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await init_db()

app.include_router(auth_router, prefix="/auth", tags=["auth"])



load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")



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
    dialog_context: dict = None

@app.get("/")
def root():
    return {"message": "Hello from WorkflowX API!"}

def schedule_google_event(title: str, start_datetime: str, end_datetime: str, modifiers: dict = None) -> str:
    creds = Credentials.from_service_account_file(
        "service_account.json",  
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    service = build("calendar", "v3", credentials=creds)
    
    event_body = {
        "summary": title,
        "start": {
            "dateTime": start_datetime,
            "timeZone": "America/Indiana/Indianapolis"
        },
        "end": {
            "dateTime": end_datetime,
            "timeZone": "America/Indiana/Indianapolis"
        },
    }
    
    if modifiers:
        if 'meeting_type' in modifiers:
            meeting_type = modifiers['meeting_type']
            if meeting_type == 'call':
                event_body["description"] = "Conference call - dial-in details will be provided."
            elif meeting_type == 'video':
                event_body["conferenceData"] = {
                    "createRequest": {
                        "requestId": f"meeting-{int(datetime.datetime.now().timestamp())}"
                    }
                }
            elif meeting_type == 'in_person':
                event_body["location"] = "Office Main Conference Room"
                
        if 'attendees' in modifiers:
            attendee_list = []
            attendees = modifiers['attendees'].split(',')
            for attendee in attendees:
                attendee = attendee.strip()
                if '@' in attendee:
                    attendee_list.append({"email": attendee})
                else:
                    attendee_list.append({"displayName": attendee, "email": "placeholder@example.com"})
            if attendee_list:
                event_body["attendees"] = attendee_list
                
        if 'priority' in modifiers and modifiers['priority'] == 'high':
            if "description" not in event_body:
                event_body["description"] = "HIGH PRIORITY MEETING"
            else:
                event_body["description"] = "HIGH PRIORITY MEETING\n\n" + event_body["description"]
            event_body["summary"] = "❗ " + event_body["summary"]
    
    if modifiers and 'meeting_type' in modifiers and modifiers['meeting_type'] == 'video':
        created_event = service.events().insert(
            calendarId="abchhatkuli@gmail.com",
            body=event_body,
            conferenceDataVersion=1
        ).execute()
    else:
        created_event = service.events().insert(
            calendarId="abchhatkuli@gmail.com",
            body=event_body
        ).execute()
        
    return created_event.get("htmlLink", "No link found")

def parse_event_time(user_text: str):
    local_tz = pytz.timezone("America/Indiana/Indianapolis")
    now_local = datetime.datetime.now(local_tz)
    modified_text = user_text.lower()
    duration_hours = 1

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

    weekday_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
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
        days_to_add = 7 - current_weekday + target_weekday
        if days_to_add >= 7:
            days_to_add = days_to_add % 7
        days_to_add += 7
        dt_local = now_local + datetime.timedelta(days=days_to_add)
    else:
        dt_local = now_local

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
        dt_local = dt_local.replace(hour=15, minute=0, second=0, microsecond=0)

    end_dt_local = dt_local + datetime.timedelta(hours=duration_hours)
    return dt_local.isoformat(), end_dt_local.isoformat()

def extract_email_and_message(user_text: str):
    normalized_text = normalize_text(user_text)
    email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
    to_match = re.search(r'(?:to|for|towards?|with|unto)\s+(' + email_regex + r')', normalized_text, re.IGNORECASE)
    if to_match:
        email = to_match.group(1)
        leftover = re.sub(r'(?:to|for|towards?|with|unto)\s+' + re.escape(email), '', normalized_text)
    else:
        m = re.search(email_regex, normalized_text)
        if m:
            email = m.group(0)
            leftover = normalized_text.replace(email, "")
        else:
            email = None
            leftover = normalized_text

    # strip out the “send/draft” verb
    leftover = re.sub(r'(?:send|write|compose|draft|create)\s+(?:an?|the)?\s*(?:email|mail|message|note)', '', leftover)

    # explicit subject
    explicit_subject = None
    subj_m = re.search(r'(?:with\s+subject|subject\s*:)\s*["\']?([^"\']+)["\']?', leftover, re.IGNORECASE)
    if subj_m:
        explicit_subject = subj_m.group(1).strip()
        leftover = re.sub(subj_m.group(0), '', leftover, flags=re.IGNORECASE)

    # sender name
    sender_name = None
    snd_m = re.search(r'(?:from|by)\s+([A-Za-z][A-Za-z ]+)', leftover)
    if snd_m:
        sender_name = snd_m.group(1).strip().title()
        leftover = re.sub(snd_m.group(0), '', leftover)

    # **here** we introduce recipient_name (you can enhance later if you want to pull “to John”)
    recipient_name = None

    leftover = re.sub(r'(?:saying|that\s+says|about|regarding)', '', leftover).strip()
    if not leftover:
        leftover = "Please see below."

    # now we return 5 values so unpacking always works
    return email, leftover, explicit_subject, sender_name, recipient_name


def generate_email_content(instructions: str, explicit_subject=None, sender_name=None, recipient_email=None):
    if explicit_subject:
        subject = explicit_subject
    else:
        subject_prompt = (
            "Create a concise yet clear email subject line for a professional email, based on these instructions: "
            f"'{instructions}'. "
            "Return ONLY the subject line text, no quotes or explanations."
        )
        subject_resp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an AI specialized in writing short, professional email subjects that capture the essence of communication intent."},
                {"role": "user", "content": subject_prompt},
            ],
            max_tokens=60,
            temperature=0.7,
        )
        subject = subject_resp.choices[0].message.content.strip()

    recipient_name = "Recipient"
    if recipient_email:
        email_parts = recipient_email.split('@')[0]
        if '.' in email_parts:
            name_parts = email_parts.split('.')
            recipient_name = ' '.join(part.capitalize() for part in name_parts)
        elif '_' in email_parts:
            name_parts = email_parts.split('_')
            recipient_name = ' '.join(part.capitalize() for part in name_parts)
        else:
            recipient_name = email_parts.capitalize()

    sender_name = sender_name or "Your Name"

    body_prompt = (
        f"Write a professional email body for an email with subject: '{subject}', based on these instructions: "
        f"'{instructions}'. "
        f"The email is FROM: {sender_name} TO: {recipient_name} ({recipient_email}). "
        f"Include proper greeting to {recipient_name} and sign-off from {sender_name}. "
        f"Replace any placeholders like [your name] with {sender_name} and [recipient] with {recipient_name}. "
        f"Make it concise but comprehensive."
    )
    body_resp = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an AI specialized in writing professional, well-structured email content."},
            {"role": "user", "content": body_prompt},
        ],
        max_tokens=300,
        temperature=0.7,
    )
    body = body_resp.choices[0].message.content.strip()
    
    replacements = {
        "[your name]": sender_name,
        "[sender]": sender_name,
        "[recipient]": recipient_name,
        "[recipient name]": recipient_name,
    }
    
    for placeholder, replacement in replacements.items():
        body = body.replace(placeholder, replacement)

    return subject, body

def extract_slack_channel_and_message(user_text: str):
    from nlp_datetime_cleaner import normalize_text
    import openai
    
    original_text = user_text
    cleaned_text = re.sub(r'send\s+send', 'send', user_text, flags=re.IGNORECASE)
    normalized_text = normalize_text(cleaned_text)
    
    channel = "#general"
    channel_identified = False
    is_ai_generated = False
    channel_part = ""
    
    quoted_msg_match = re.search(r'["\'](.*?)["\']', original_text)
    quoted_message = None
    if quoted_msg_match:
        quoted_message = quoted_msg_match.group(1).strip()
        normalized_text = re.sub(r'["\'](.*?)["\']', 'QUOTED_TEXT', normalized_text)
    
    channel_patterns = [
        r'(?:to|in|on|at|for|into)\s+(?:the\s+)?(?:channel\s+)?(#[\w\-\.]+)',
        r'(?:to|in|on|at|for|into)\s+(?:the\s+)?channel\s+([a-z0-9_\-\.]+)',
        r'(?:to|in|on|at|for|into)\s+(?:the\s+)?([a-z0-9_\-\.]+)(?:\s+channel)?',
        r'channel\s+([a-z0-9_\-\.]+)',
        r'(?:slack|message|msg|post)(?:\s+to|\s+in|\s+on|\s+at)?\s+([a-z0-9_\-\.]+)',
        r'(?:all-[a-z0-9_\-\.]+)'
    ]
    
    for pattern in channel_patterns:
        matches = re.finditer(pattern, normalized_text, re.IGNORECASE)
        for match in matches:
            if pattern == r'(?:all-[a-z0-9_\-\.]+)':
                candidate = match.group(0).strip()
            else:
                candidate = match.group(1).strip()
            common_words = ['slack', 'message', 'channel', 'say', 'post', 'send', 'team', 
                          'msg', 'the', 'a', 'an', 'this', 'that', 'there', 'here', 'people',
                          'everyone', 'somebody', 'anyone', 'text', 'dm', 'group']
            if candidate.lower() == 'team' and pattern.find(r'([a-z0-9_\-\.]+)') != -1:
                team_context_match = re.search(r'(\w+)\s+team', normalized_text, re.IGNORECASE)
                if team_context_match:
                    candidate = team_context_match.group(1).strip()
            if candidate.lower() not in common_words and len(candidate) >= 2:
                if not candidate.startswith('#'):
                    channel = f"#{candidate}"
                else:
                    channel = candidate
                channel_identified = True
                channel_part = match.group(0)
                break
        if channel_identified:
            break
    
    if quoted_message:
        return channel, quoted_message, False
    
    clean_text = normalized_text
    command_patterns = [
        r'^(?:send|post|write)\s+(?:a\s+)?(?:slack|message|msg)(?:\s+message)?\s+(?:to|in|on|at|for|into)\s+(?:the\s+)?(?:channel\s+)?\S+\s+',
        r'^(?:slack|send|post|message)\s+(?:to|in|on|at|for|into)\s+(?:the\s+)?(?:channel\s+)?\S+\s+',
        r'^(?:send|post|write)\s+(?:a\s+)?(?:slack|message|msg)(?:\s+message)?\s+'
    ]
    
    for pattern in command_patterns:
        clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)
    
    if channel_identified and channel_part:
        clean_text = re.sub(re.escape(channel_part), '', clean_text, flags=re.IGNORECASE).strip()
    
    content_patterns = [
        r'^(?:saying|with message|that says|with text|with content|saying that|saying|that|:)\s+(.*)',
        r'^(?:ask|tell|announce|share|write)\s+(.*)',
        r'^(?:and|to)\s+(?:say|ask|tell|post)\s+(.*)'
    ]
    
    message = None
    for pattern in content_patterns:
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            message = match.group(1).strip()
            if message:
                break
    
    if not message and clean_text.strip():
        message = clean_text.strip()
    
    if original_text.lower().find("asking when the meeting is") != -1 or original_text.lower().find("ask when the meeting is") != -1:
        message = "When is the meeting?"
    elif "asking when" in original_text.lower() or "ask when" in original_text.lower():
        when_match = re.search(r'(?:asking|ask)\s+when\s+(.*?)(?:\s*\?|$)', original_text.lower())
        if when_match:
            what = when_match.group(1).strip()
            message = f"When {what}?"
    elif "asking where" in original_text.lower() or "ask where" in original_text.lower():
        where_match = re.search(r'(?:asking|ask)\s+where\s+(.*?)(?:\s*\?|$)', original_text.lower())
        if where_match:
            what = where_match.group(1).strip()
            message = f"Where {what}?"
    elif message and message.lower().startswith(('ask', 'asking')):
        question_match = re.search(r'(?:ask|asking)(?:\s+\w+)?\s+(.*)', message, re.IGNORECASE)
        if question_match:
            question = question_match.group(1).strip()
            if len(question) > 5:
                if not any(question.lower().startswith(q) for q in ['when', 'what', 'where', 'who', 'how', 'why']):
                    if 'when' in question.lower():
                        question = f"When {question}?"
                    elif 'where' in question.lower():
                        question = f"Where {question}?"
                    elif 'what' in question.lower():
                        question = f"What {question}?"
                    else:
                        question = f"{question}?"
                message = question
    
    if not message or message in ["people", "them", "everyone"] or len(message) < 5:
        try:
            prompt = f"Generate a friendly, concise Slack message for channel {channel} based on this intent: '{original_text}'. If it's asking about a meeting time, make it a natural question about when the meeting is scheduled. Keep it under 20 words and make it sound conversational, not like a command."
            
            msg_resp = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an assistant that generates concise, appropriate Slack messages based on user intent."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=60,
                temperature=0.7,
            )
            message = msg_resp.choices[0].message.content.strip()
            message = re.sub(r'^[\'"]|[\'"]$', '', message)
            is_ai_generated = True
        except Exception as e:
            print(f"Error generating Slack message with GPT: {e}")
            message = "Does anyone know when our next meeting is scheduled?"
            is_ai_generated = True
    
    return channel, message, is_ai_generated

@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    from nlp_datetime_cleaner import normalize_text
    original_text = req.message
    user_text = normalize_text(original_text)
    print(f"Original text: {original_text}")
    print(f"Normalized text: {user_text}")

    if "test calendar" in user_text:
        duration_hours = 1
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
        local_tz = pytz.timezone("America/Indiana/Indianapolis")
        now_local = datetime.datetime.now(local_tz)
        tomorrow_2pm_local = (now_local + datetime.timedelta(days=3)).replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        end_local = tomorrow_2pm_local + datetime.timedelta(hours=duration_hours)
        start_str = tomorrow_2pm_local.isoformat()
        end_str = end_local.isoformat()
        event_link = schedule_google_event(
            title=f"Test Calendar Event ({duration_hours} hour{'s' if duration_hours != 1 else ''})",
            start_datetime=start_str,
            end_datetime=end_str
        )
        return {"reply": f"Test event scheduled for {duration_hours} hour{'s' if duration_hours != 1 else ''}! Event link: {event_link}"}

    classification_text = bert_classify(user_text)
    print("💡 NLP Classification:", classification_text)

    if "schedule_meeting" in classification_text:
        from nlp_datetime_cleaner import extract_intent_modifiers
        modifiers = extract_intent_modifiers(original_text, "schedule_meeting")
        print(f"Extracted modifiers: {modifiers}")
        normalized_text = normalize_datetime_input(user_text)
        print(f"Date-normalized text: {normalized_text}")
        start_dt_obj, end_dt_obj = intelligent_date_parse(normalized_text)
        if start_dt_obj and end_dt_obj:
            start_dt = start_dt_obj.isoformat()
            end_dt = end_dt_obj.isoformat()
            print(f"Intelligent parser result: start={start_dt}, end={end_dt}")
        else:
            ai_response = ai_clean_datetime(normalized_text)
            print(f"AI response: {ai_response}")
            match = re.search(r"START=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\s+END=(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})", ai_response)
            if match:
                start_dt = match.group(1)
                end_dt = match.group(2)
                print(f"AI parsed: start={start_dt}, end={end_dt}")
            else:
                print("AI parser failed, using manual parser")
                start_dt, end_dt = parse_event_time(normalized_text)
        if not start_dt:
            return {
                "reply": (
                    "Sorry, I couldn't understand the date/time. Try rephrasing it like: "
                    "'Schedule meeting on March 10 at 2 PM for 2 hours'."
                )
            }
        start_time = dateutil_parser.parse(start_dt)
        end_time = dateutil_parser.parse(end_dt)
        duration_hours = (end_time - start_time).total_seconds() / 3600
        meeting_description = extract_meeting_description(original_text)
        if meeting_description:
            meeting_title = f"Meeting: {meeting_description}"
        else:
            meeting_title = f"Meeting: {original_text.strip()[:50]}"
        if 'meeting_type' in modifiers:
            meeting_type = modifiers['meeting_type']
            if meeting_type == 'call':
                meeting_title = f"📞 Call: {meeting_description or original_text.strip()[:50]}"
            elif meeting_type == 'video':
                meeting_title = f"📹 Video: {meeting_description or original_text.strip()[:50]}"
            elif meeting_type == 'in_person':
                meeting_title = f"👥 In-Person: {meeting_description or original_text.strip()[:50]}"
            elif meeting_type == 'interview':
                meeting_title = f"🤝 Interview: {meeting_description or original_text.strip()[:50]}"
            elif meeting_type == '1on1':
                meeting_title = f"👤 1-on-1: {meeting_description or original_text.strip()[:50]}"
        event_link = schedule_google_event(
            meeting_title, 
            start_dt, 
            end_dt,
            modifiers
        )
        start_time_local = start_time.strftime("%A, %B %d at %I:%M %p")
        reply = f"Meeting scheduled for {start_time_local} with a duration of {int(duration_hours)} hour{'s' if duration_hours != 1 else ''}!"
        if 'meeting_type' in modifiers:
            meeting_type = modifiers['meeting_type']
            if meeting_type == 'call':
                reply += " Conference call details will be sent to participants."
            elif meeting_type == 'video':
                reply += " Video conference link is included in the calendar invitation."
            elif meeting_type == 'in_person':
                reply += " Meeting will be held in person at the office."
        if 'attendees' in modifiers:
            reply += f" Attendees: {modifiers['attendees']}."
        reply += f" Event link: {event_link}"
        return {"reply": reply}
        
    elif "send_email" in classification_text or (req.dialog_context and req.dialog_context.get("waiting_for") == "recipient_email"):
        dc = req.dialog_context or {}

        # 1) If we're waiting for the email, grab it
        if dc.get("waiting_for") == "recipient_email":
            dc["recipient_email"] = original_text.strip()
        else:
            # 2) First turn: parse out whatever we can
            rec_email, instructions, explicit_subject, sender_name, recipient_name = extract_email_and_message(original_text)
            dc = {
                "instructions": instructions,
                "explicit_subject": explicit_subject,
                "sender_name": sender_name,
                "recipient_name": recipient_name,
                "recipient_email": rec_email
            }

        # 3) If no valid email yet, ask once
        email_regex = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
        if not dc.get("recipient_email") or not re.match(email_regex, dc["recipient_email"]):
            whom = dc.get("recipient_name") or "the recipient"
            return {
                "reply": f"What’s {whom}’s email address?",
                "dialog_context": {**dc, "waiting_for": "recipient_email"}
            }

        # 4) We have a valid email — build & send
        sender = dc.get("sender_name") or "Your Name"
        subject, body = generate_email_content(
            dc["instructions"],
            explicit_subject=dc["explicit_subject"],
            sender_name=sender,
            recipient_email=dc["recipient_email"]
        )
        sent = send_gmail(dc["recipient_email"], subject, body)
        if sent:
            return {
                "reply": f"Email sent to {dc['recipient_email']} with subject “{subject}”."
            }
        else:
            return {"reply": "Sorry, I couldn’t send that email. Please try again."}

        
    elif "send_slack" in classification_text or "slack_send" in classification_text:
        channel, text, is_ai_generated = extract_slack_channel_and_message(original_text)
        is_quoted = bool(re.search(r'["\'](.*?)["\']', original_text))
        success = send_slack_message(channel, text)
        if success:
            if is_quoted:
                return {"reply": f"Slack message sent to {channel} with your exact message: '{text}'"}
            elif is_ai_generated:
                return {"reply": f"Slack message sent to {channel}: '{text}'\n\nNote: I generated this message based on your instructions. Use quotes for exact messages."}
            else:
                return {"reply": f"Slack message sent to {channel}: '{text}'"}
        else:
            return {"reply": f"Failed to send Slack message to {channel}. Please check the channel name and try again."}

    elif "retrieve_slack" in classification_text or "slack_retrieve" in classification_text:
        channel, count, search_term = extract_slack_retrieve_params(original_text)
        try:
            messages = get_latest_slack_messages(channel, count, search_term)
        except TypeError:
            try:
                messages = get_latest_slack_messages(channel, count)
                if search_term:
                    search_note = f"\n\nNote: Message filtering by content '{search_term}' is not yet implemented."
            except TypeError:
                messages = get_latest_slack_messages(channel)
        reply_str = f"Latest {count} messages from {channel}"
        if search_term:
            reply_str += f" containing '{search_term}'"
        reply_str += ":\n\n"
        if not messages or len(messages) == 0:
            return {"reply": f"No messages found in {channel} or an error occurred."}
        for msg in messages:
            user = msg.get("user", "unknown")
            text = msg.get("text", "")
            timestamp = msg.get("ts", "")
            time_str = ""
            if timestamp:
                try:
                    from datetime import datetime
                    msg_time = datetime.fromtimestamp(float(timestamp))
                    time_str = f" ({msg_time.strftime('%m/%d %I:%M %p')})"
                except:
                    pass
            reply_str += f"👤 **{user}**{time_str}:\n{text}\n\n"
        if search_term and 'search_note' in locals():
            reply_str += search_note
        return {"reply": reply_str}
    
    elif "retrieve_email" in classification_text:
        count = 5
        count_match = re.search(r'(last|recent|top)\s+(\d+)', user_text)
        if count_match:
            try:
                count = int(count_match.group(2))
                count = min(max(count, 1), 20)
            except:
                pass
        sender_filter = None
        email_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
        email_match = re.search(email_pattern, user_text)
        if email_match:
            sender_filter = email_match.group(0)
        else:
            name_pattern = r'[\w\s\'\-\.]+'
            from_name_match = re.search(f'from\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE)
            if from_name_match:
                sender_filter = from_name_match.group(1).strip()
            elif re.search(f'by\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE):
                by_match = re.search(f'by\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE)
                sender_filter = by_match.group(1).strip()
            elif re.search(f'sent\\s+by\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE):
                sent_match = re.search(f'sent\\s+by\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE)
                sender_filter = sent_match.group(1).strip()
            elif re.search(f'(?:emails?|messages?)\\s+(?:with|containing|from)\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE):
                name_match = re.search(f'(?:emails?|messages?)\\s+(?:with|containing|from)\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE)
                sender_filter = name_match.group(1).strip()
            elif re.search(f'show\\s+(?:me\\s+)?(?:emails?|messages?)\\s+from\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE):
                show_match = re.search(f'show\\s+(?:me\\s+)?(?:emails?|messages?)\\s+from\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE)
                sender_filter = show_match.group(1).strip()
        if sender_filter and len(sender_filter) > 50:
            sender_filter = sender_filter[:50]
        subject_filter = None
        subject_match = re.search(r'(?:with|about|containing|subject)\s+["\']?([^"\']+)["\']?', user_text)
        if subject_match:
            subject_filter = subject_match.group(1)
        emails_summary = get_latest_emails(count, sender_filter)
        if subject_filter and sender_filter is None and "No emails found" not in emails_summary:
            filter_note = f"\n\nNote: Email filtering by subject ('{subject_filter}') is not yet implemented."
            emails_summary += filter_note
        if not emails_summary:
            return {"reply": "No emails found or an error occurred."}
        return {"reply": emails_summary}
    
    elif "create_crm" in classification_text:
        # Use the original text to extract the full name and email
        name_match = re.search(r'named\s+([A-Za-z]+(?:\s+[A-Za-z]+)+)', original_text)
        if name_match:
            full_name = name_match.group(1).strip()
            parts = full_name.split()
            firstname = parts[0]
            lastname = parts[1]  # only take first two parts (ignore middle names)
        else:
            firstname = "Unknown"
            lastname = ""
        email_match = re.search(r'(?:email\s*(?:is|:)?\s*)(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b)', original_text)
        email = email_match.group(1) if email_match else "unknown@example.com"
        new_id = create_hubspot_contact(firstname, lastname, email)
        if new_id:
            return {"reply": f"Created new HubSpot contact with ID: {new_id}"}
        else:
            return {"reply": "Failed to create new HubSpot contact."}

    elif "update_crm" in classification_text:
        # --- Specialized update patterns ---
        # Pattern 1: Update name using an email identifier.
        match_name = re.search(
            r'(?:update|change)\s+(?:hubspot|crm)\s+name\s+of\s+(\S+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\s+to\s+([A-Za-z]+\s+[A-Za-z]+)',
            user_text, re.IGNORECASE)
        if match_name:
            identifier_email = match_name.group(1).strip()
            new_name = match_name.group(2).strip()
            parts = new_name.split()
            new_firstname = parts[0]
            new_lastname = parts[1]
            from hubspot_integration import find_hubspot_contact_by_email
            contact_id = find_hubspot_contact_by_email(identifier_email)
            if not contact_id:
                return {"reply": f"Couldn't find a HubSpot contact with email {identifier_email}."}
            updated_id = update_hubspot_contact(contact_id, new_firstname, new_lastname, None)
            if updated_id:
                return {"reply": f"Updated HubSpot contact {updated_id} successfully."}
            else:
                return {"reply": f"Failed to update contact with id {contact_id}."}
        # Pattern 2: Update email using a name identifier.
        match_email = re.search(
            r'(?:update|change)\s+(?:hubspot|crm)\s+email\s+for\s+([A-Za-z]+\s+[A-Za-z]+)\s+to\s+(\S+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})',
            user_text, re.IGNORECASE)
        if match_email:
            identifier_name = match_email.group(1).strip()
            new_email = match_email.group(2).strip()
            
            contacts = get_hubspot_contacts(limit=50)
            contact_id = None
            for c in contacts:
                full_name = f"{c.get('firstname','').strip()} {c.get('lastname','').strip()}".strip()
                if full_name.lower() == identifier_name.lower():
                    contact_id = c.get("id")
                    break
            if not contact_id:
                return {"reply": f"Couldn't find a HubSpot contact with name {identifier_name}."}
            updated_id = update_hubspot_contact(contact_id, None, None, new_email)
            if updated_id:
                return {"reply": f"Updated HubSpot contact {updated_id} successfully."}
            else:
                return {"reply": f"Failed to update contact with id {contact_id}."}
        # --- Fallback update logic ---
        contact_id = None
        identifier = None
        id_match = re.search(r'\b(?:id\s*[:#]?\s*)(\d+)\b', user_text, re.IGNORECASE)
        if id_match:
            contact_id = id_match.group(1)
        else:
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', user_text)
            if emails and len(emails) >= 2:
                identifier = emails[0]
                new_email = emails[1]
            elif emails:
                identifier = emails[0]
        if not contact_id and not identifier:
            name_match = re.search(r'named\s+([A-Za-z]+\s+[A-Za-z]+)', user_text)
            if name_match:
                identifier = name_match.group(1).strip()
        if not contact_id and identifier:
            if re.match(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', identifier):
                from hubspot_integration import find_hubspot_contact_by_email
                contact_id = find_hubspot_contact_by_email(identifier)
                if not contact_id:
                    return {"reply": f"Couldn't find a HubSpot contact with email {identifier}."}
        if not contact_id:
            return {"reply": "I couldn't identify the HubSpot contact to update. Please specify an id, email, or full name."}
        new_email_match = re.search(r'\bto\s+(\S+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', user_text)
        new_email = new_email_match.group(1) if new_email_match else None
        new_firstname = None
        new_lastname = None
        first_name_match = re.search(r'first\s+name\s+([A-Za-z]+)', user_text)
        if first_name_match:
            new_firstname = first_name_match.group(1)
        last_name_match = re.search(r'(?:last\s+name|surname|family\s+name)\s+([A-Za-z]+)', user_text)
        if last_name_match:
            new_lastname = last_name_match.group(1)
        new_name_match = re.search(r'\bto\s+([A-Za-z]+\s+[A-Za-z]+)', user_text)
        if not new_email and new_name_match:
            new_name = new_name_match.group(1).strip()
            parts = new_name.split()
            new_firstname = parts[0]
            new_lastname = parts[1]
        updated_id = update_hubspot_contact(contact_id, new_firstname, new_lastname, new_email)
        if updated_id:
            return {"reply": f"Updated HubSpot contact {updated_id} successfully."}
        else:
            return {"reply": f"Failed to update contact with id {contact_id}."}
        
    elif "retrieve_crm" in classification_text:
        from hubspot_integration import get_hubspot_contacts_dual
        contacts_dual = get_hubspot_contacts_dual(limit_each=5)

        if not contacts_dual or (not contacts_dual["top"] and not contacts_dual["bottom"]):
            return {"reply": "No contacts found in HubSpot or an error occurred."}

        reply_lines = ["📋 **Top 5 Newest Contacts:**"]
        for c in contacts_dual["top"]:
            line = f"👤 {c.get('firstname', 'Unknown')} {c.get('lastname', '')} - {c.get('email', 'No email')}"
            reply_lines.append(line)

        reply_lines.append("\n📁 **Bottom 5 Oldest Contacts:**")
        for c in contacts_dual["bottom"]:
            line = f"👤 {c.get('firstname', 'Unknown')} {c.get('lastname', '')} - {c.get('email', 'No email')}"
            reply_lines.append(line)

        return {"reply": "\n".join(reply_lines)}


    
    else:
        final_resp = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant for WorkflowX. You can help with scheduling meetings, sending emails, and retrieving information. Provide concise, helpful responses.",
                },
                {"role": "user", "content": original_text},
            ],
            max_tokens=150,
            temperature=0.7,
        )
        ai_text = final_resp.choices[0].message.content.strip()
        return {"reply": ai_text}

def extract_meeting_description(text):
    about_match = re.search(r'(?:about|regarding|concerning|for|on)\s+([^.,!?]+)', text, re.IGNORECASE)
    if about_match:
        return about_match.group(1).strip()
    with_match = re.search(r'(?:with|to discuss|to talk about)\s+([^.,!?]+)', text, re.IGNORECASE)
    if with_match:
        return with_match.group(1).strip()
    return None

def extract_slack_retrieve_params(user_text):
    from nlp_datetime_cleaner import normalize_text
    normalized = normalize_text(user_text)
    channel = "#general"
    count = 5
    search_term = None
    channel_patterns = [
        r'from\s+(#[\w-]+)',
        r'in\s+(#[\w-]+)',
        r'on\s+(#[\w-]+)',
        r'channel\s+(#[\w-]+)',
        r'from\s+(?:channel\s+)?([a-z0-9_-]+)(?:\s+channel)?',
        r'in\s+(?:channel\s+)?([a-z0-9_-]+)(?:\s+channel)?',
        r'on\s+(?:channel\s+)?([a-z0-9_-]+)(?:\s+channel)?'
    ]
    for pattern in channel_patterns:
        match = re.search(pattern, normalized)
        if match:
            channel_name = match.group(1)
            if not channel_name.startswith('#'):
                common_words = ['slack', 'message', 'channel', 'messages', 'history', 'conversation', 'chat', 'all']
                if channel_name.lower() not in common_words:
                    channel = f"#{channel_name}"
            else:
                channel = channel_name
            break
    count_patterns = [
        r'(?:last|recent|latest|top)\s+(\d+)',
        r'(\d+)\s+(?:messages|posts)',
        r'show\s+(?:me\s+)?(\d+)'
    ]
    for pattern in count_patterns:
        match = re.search(pattern, normalized)
        if match:
            try:
                count = int(match.group(1))
                count = min(max(count, 1), 20)
                break
            except:
                pass
    search_patterns = [
        r'(?:containing|with|about|mentioning|related to|that mention|that has|having)\s+["\']?([^"\'.,!?]+)["\']?',
        r'search\s+for\s+["\']?([^"\'.,!?]+)["\']?'
    ]
    for pattern in search_patterns:
        match = re.search(pattern, normalized)
        if match:
            search_term = match.group(1).strip()
            if search_term:
                break
    return channel, count, search_term
