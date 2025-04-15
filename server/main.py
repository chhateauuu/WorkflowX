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
from server.hubspot_integration import get_hubspot_contacts, create_hubspot_contact, update_hubspot_contact
from server.refined_nlp import bert_classify
from server.nlp_datetime_cleaner import ai_clean_datetime, normalize_datetime_input, intelligent_date_parse, normalize_text





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
    dialog_context: dict = None

@app.get("/")
def root():
    return {"message": "Hello from WorkflowX API!"}

def schedule_google_event(title: str, start_datetime: str, end_datetime: str, modifiers: dict = None) -> str:
    """
    Enhanced version of schedule_google_event that handles advanced meeting parameters.
    """
    creds = Credentials.from_service_account_file(
        "service_account.json",  
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    service = build("calendar", "v3", credentials=creds)
    
    # Start with basic event body
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
    
    # Process modifiers if provided
    if modifiers:
        # Handle meeting type
        if 'meeting_type' in modifiers:
            meeting_type = modifiers['meeting_type']
            
            # Add location or conference data based on meeting type
            if meeting_type == 'call':
                event_body["description"] = "Conference call - dial-in details will be provided."
            elif meeting_type == 'video':
                # Add a Google Meet link by default
                event_body["conferenceData"] = {
                    "createRequest": {
                        "requestId": f"meeting-{int(datetime.datetime.now().timestamp())}"
                    }
                }
            elif meeting_type == 'in_person':
                event_body["location"] = "Office Main Conference Room"
                
        # Handle attendees
        if 'attendees' in modifiers:
            attendee_list = []
            attendees = modifiers['attendees'].split(',')
            
            for attendee in attendees:
                attendee = attendee.strip()
                # If it looks like an email, add directly
                if '@' in attendee:
                    attendee_list.append({"email": attendee})
                else:
                    # Otherwise add as display name
                    attendee_list.append({"displayName": attendee, "email": "placeholder@example.com"})
                    
            if attendee_list:
                event_body["attendees"] = attendee_list
                
        # Handle priority
        if 'priority' in modifiers and modifiers['priority'] == 'high':
            if "description" not in event_body:
                event_body["description"] = "HIGH PRIORITY MEETING"
            else:
                event_body["description"] = "HIGH PRIORITY MEETING\n\n" + event_body["description"]
                
            # Also update the title to indicate priority
            event_body["summary"] = "❗ " + event_body["summary"]
    
    # Create the event with processed parameters
    if modifiers and 'meeting_type' in modifiers and modifiers['meeting_type'] == 'video':
        # For video meetings, enable conferencing
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
    """
    Parses user text to determine meeting start and end time.
    Handles phrases like "next Wednesday at 3pm for 2 hours" or "Wednesday next week at 2pm".
    Returns (start_time, end_time) in ISO format.
    """
    local_tz = pytz.timezone("America/Indiana/Indianapolis")
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
    Advanced extraction of email addresses and message content from user text.
    Handles various formats and colloquialisms.
    Returns (email, user_instructions, explicit_subject, sender_name).
    """
    # Normalize the text to handle typos and standardize
    normalized_text = normalize_text(user_text)
    
    # Comprehensive email regex
    email_regex = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    
    # Try to find recipient "to X@Y.com"
    to_match = re.search(r'(?:to|for|towards?|with|unto)\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})', normalized_text, re.IGNORECASE)
    if to_match:
        email = to_match.group(1)
        # Remove the "to email" part
        leftover = re.sub(r'(?:to|for|towards?|with|unto)\s+' + re.escape(email), '', normalized_text)
    else:
        # Try to find any email address
        email_match = re.search(email_regex, normalized_text)
        if email_match:
            email = email_match.group(0)
            # Remove just the email
            leftover = normalized_text.replace(email, "")
        else:
            # No email found, use placeholder
            email = "someone@example.com"
            leftover = normalized_text
    
    # Clean up email command indicators
    leftover = re.sub(r'(?:send|write|compose|draft|create)\s+(?:an?|the)?\s*(?:email|mail|message|note)', '', leftover)
    
    # Extract subject if explicitly mentioned
    subject_match = re.search(r'(?:with\s+subject|with\s+title|subject\s*:|title\s*:)\s*["\']?([^"\']+)["\']?', leftover, re.IGNORECASE)
    explicit_subject = None
    if subject_match:
        explicit_subject = subject_match.group(1).strip()
        # Remove the subject part from leftover
        leftover = re.sub(r'(?:with\s+subject|with\s+title|subject\s*:|title\s*:)\s*["\']?([^"\']+)["\']?', '', leftover, flags=re.IGNORECASE)
    
    # Extract sender information if mentioned - using a more restrictive pattern for names
    # Look for "from name" format where name is just 1-3 words (a typical name)
    sender_match = re.search(r'(?:from|by|sent\s+by|written\s+by)\s+([a-zA-Z0-9_]+(?:\s+[a-zA-Z0-9_]+){0,2})\b', leftover, re.IGNORECASE)
    sender_name = None
    if sender_match:
        sender_name = sender_match.group(1).strip()
        # Remove the sender part from leftover
        leftover = re.sub(r'(?:from|by|sent\s+by|written\s+by)\s+' + re.escape(sender_name) + r'\b', '', leftover, flags=re.IGNORECASE)
    
    # Clean up other common phrases
    leftover = re.sub(r'(?:saying|telling|stating|that\s+says|informing)\s+(?:that|him|her|them)?', '', leftover)
    leftover = re.sub(r'(?:about|regarding|concerning|on\s+the\s+topic\s+of)', '', leftover)
    
    # Handle empty instructions
    leftover = leftover.strip()
    if not leftover:
        leftover = "Please find the information you requested."
    
    return email, leftover, explicit_subject, sender_name

def generate_email_content(instructions: str, explicit_subject=None, sender_name=None, recipient_email=None):
    """
    Enhanced email content generator that uses GPT to produce a subject and body.
    Now supports explicit subject override and improved prompting.
    
    Parameters:
    - instructions: The instructions for what the email should say
    - explicit_subject: Optional explicit subject provided by the user
    - sender_name: The name of the person sending the email
    - recipient_email: The email address of the recipient
    
    Returns: (subject, body)
    """
    # If explicit subject was provided, use it
    if explicit_subject:
        subject = explicit_subject
    else:
        # Generate subject with GPT
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

    # Extract recipient name from email if possible
    recipient_name = "Recipient"
    if recipient_email:
        # Try to extract a name from the email
        email_parts = recipient_email.split('@')[0]
        # Convert formats like john.doe or john_doe to John Doe
        if '.' in email_parts:
            name_parts = email_parts.split('.')
            recipient_name = ' '.join(part.capitalize() for part in name_parts)
        elif '_' in email_parts:
            name_parts = email_parts.split('_')
            recipient_name = ' '.join(part.capitalize() for part in name_parts)
        else:
            # Just capitalize the username part
            recipient_name = email_parts.capitalize()

    # Default sender name if not provided
    sender_name = sender_name or "Your Name"

    # Generate body with GPT - now with enhanced context
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
    
    # Manual replacement of common placeholders
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
    """
    Advanced extraction of Slack channel and message content from user input.
    Handles various formats, colloquialisms, quoted text as exact messages,
    and generates appropriate messages for vague instructions.
    Returns (channel, message, is_ai_generated).
    """
    from server.nlp_datetime_cleaner import normalize_text
    import openai
    
    # Save original text for quoted message extraction
    original_text = user_text
    
    # Normalize the text to handle typos and standardize
    # Removing duplicate "send send" patterns first
    cleaned_text = re.sub(r'send\s+send', 'send', user_text, flags=re.IGNORECASE)
    normalized_text = normalize_text(cleaned_text)
    
    # Default channel if none specified
    channel = "#general"
    channel_identified = False
    is_ai_generated = False
    channel_part = ""
    
    # Extract quoted text first - this is highest priority for exact messages
    quoted_msg_match = re.search(r'["\'](.*?)["\']', original_text)
    quoted_message = None
    if quoted_msg_match:
        quoted_message = quoted_msg_match.group(1).strip()
        # Remove the quoted text to help with channel extraction
        normalized_text = re.sub(r'["\'](.*?)["\']', 'QUOTED_TEXT', normalized_text)
    
    # Enhanced channel extraction patterns - ordered by specificity
    channel_patterns = [
        # Very explicit channel mentions with # symbol
        r'(?:to|in|on|at|for|into)\s+(?:the\s+)?(?:channel\s+)?(#[\w\-\.]+)',
        
        # Channel mentions with "channel" keyword
        r'(?:to|in|on|at|for|into)\s+(?:the\s+)?channel\s+([a-z0-9_\-\.]+)',
        
        # Direct channel mentions without "channel" keyword but with preposition
        r'(?:to|in|on|at|for|into)\s+(?:the\s+)?([a-z0-9_\-\.]+)(?:\s+channel)?',
        
        # Support for direct channel name specification
        r'channel\s+([a-z0-9_\-\.]+)',
        
        # Look for channel name after slack reference
        r'(?:slack|message|msg|post)(?:\s+to|\s+in|\s+on|\s+at)?\s+([a-z0-9_\-\.]+)',
        
        # Special case for "all-" prefixed channels which are common
        r'(?:all-[a-z0-9_\-\.]+)'
    ]
    
    # Try each pattern in order of reliability
    for pattern in channel_patterns:
        matches = re.finditer(pattern, normalized_text, re.IGNORECASE)
        for match in matches:
            # Special case for all- prefixed channels (last pattern)
            if pattern == r'(?:all-[a-z0-9_\-\.]+)':
                candidate = match.group(0).strip()
            else:
                candidate = match.group(1).strip()
            
            # Skip common words that shouldn't be channels
            common_words = ['slack', 'message', 'channel', 'say', 'post', 'send', 'team', 
                          'msg', 'the', 'a', 'an', 'this', 'that', 'there', 'here', 'people',
                          'everyone', 'somebody', 'anyone', 'text', 'dm', 'group']
            
            # Special handling for channels that might include the word "team"
            if candidate.lower() == 'team' and pattern.find(r'([a-z0-9_\-\.]+)') != -1:
                # Look for words before "team" that might be the true channel name
                team_context_match = re.search(r'(\w+)\s+team', normalized_text, re.IGNORECASE)
                if team_context_match:
                    candidate = team_context_match.group(1).strip()
            
            if candidate.lower() not in common_words and len(candidate) >= 2:
                # Add # if not already present
                if not candidate.startswith('#'):
                    channel = f"#{candidate}"
                else:
                    channel = candidate
                
                # For removing the matched part when extracting message
                channel_identified = True
                channel_part = match.group(0)
                break
        
        if channel_identified:
            break
    
    # If we found a quoted message, use it directly
    if quoted_message:
        return channel, quoted_message, False
    
    # First clean up the full command preamble
    # This addresses the most common patterns like "send a slack message to channel X ..."
    clean_text = normalized_text
    command_patterns = [
        # Complete command patterns
        r'^(?:send|post|write)\s+(?:a\s+)?(?:slack|message|msg)(?:\s+message)?\s+(?:to|in|on|at|for|into)\s+(?:the\s+)?(?:channel\s+)?\S+\s+',
        r'^(?:slack|send|post|message)\s+(?:to|in|on|at|for|into)\s+(?:the\s+)?(?:channel\s+)?\S+\s+',
        # Additional patterns for other command forms
        r'^(?:send|post|write)\s+(?:a\s+)?(?:slack|message|msg)(?:\s+message)?\s+'
    ]
    
    for pattern in command_patterns:
        clean_text = re.sub(pattern, '', clean_text, flags=re.IGNORECASE)
    
    # Then specifically remove the channel part if identified
    if channel_identified and channel_part:
        clean_text = re.sub(re.escape(channel_part), '', clean_text, flags=re.IGNORECASE).strip()
    
    # Look for verbs that introduce the message content
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
            if message:  # Only use if not empty
                break
    
    # If we still don't have a message, just use whatever's left after cleanup
    if not message and clean_text.strip():
        message = clean_text.strip()
    
    # Special handling for asking/questions about meetings
    if original_text.lower().find("asking when the meeting is") != -1 or original_text.lower().find("ask when the meeting is") != -1:
        message = "When is the meeting?"
    elif "asking when" in original_text.lower() or "ask when" in original_text.lower():
        # Extract what comes after "asking when" or "ask when"
        when_match = re.search(r'(?:asking|ask)\s+when\s+(.*?)(?:\s*\?|$)', original_text.lower())
        if when_match:
            what = when_match.group(1).strip()
            message = f"When {what}?"
    elif "asking where" in original_text.lower() or "ask where" in original_text.lower():
        # Extract what comes after "asking where" or "ask where"
        where_match = re.search(r'(?:asking|ask)\s+where\s+(.*?)(?:\s*\?|$)', original_text.lower())
        if where_match:
            what = where_match.group(1).strip()
            message = f"Where {what}?"
    # For other types of questions in message
    elif message and message.lower().startswith(('ask', 'asking')):
        question_match = re.search(r'(?:ask|asking)(?:\s+\w+)?\s+(.*)', message, re.IGNORECASE)
        if question_match:
            question = question_match.group(1).strip()
            if len(question) > 5:  # Make sure it's a substantial question
                # Preserve question words at the beginning
                if not any(question.lower().startswith(q) for q in ['when', 'what', 'where', 'who', 'how', 'why']):
                    # If it doesn't start with a question word, add appropriate one based on content
                    if 'when' in question.lower():
                        question = f"When {question}?"
                    elif 'where' in question.lower():
                        question = f"Where {question}?"
                    elif 'what' in question.lower():
                        question = f"What {question}?"
                    else:
                        question = f"{question}?"
                message = question
    
    # If the message is too vague or empty, use GPT to generate a more appropriate message
    if not message or message in ["people", "them", "everyone"] or len(message) < 5:
        try:
            # Generate a message based on the general intent
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
            
            # Remove any quotes GPT might have added
            message = re.sub(r'^[\'"]|[\'"]$', '', message)
            is_ai_generated = True
            
        except Exception as e:
            print(f"Error generating Slack message with GPT: {e}")
            # Fallback to simple message
            message = "Does anyone know when our next meeting is scheduled?"
            is_ai_generated = True
    
    return channel, message, is_ai_generated

@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    from server.nlp_datetime_cleaner import normalize_text
    
    # First, normalize the user's text to fix typos and standardize format
    original_text = req.message
    user_text = normalize_text(original_text)
    print(f"Original text: {original_text}")
    print(f"Normalized text: {user_text}")

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
        local_tz = pytz.timezone("America/Indiana/Indianapolis")
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

    # Get intent classification
    classification_text = bert_classify(user_text)
    print("💡 NLP Classification:", classification_text)

    # Handle different intents with enhanced processing
    if "schedule_meeting" in classification_text:
        # First use our common normalizer
        from server.nlp_datetime_cleaner import extract_intent_modifiers
        
        # Extract intent modifiers from the original text
        modifiers = extract_intent_modifiers(original_text, "schedule_meeting")
        print(f"Extracted modifiers: {modifiers}")
        
        # Use the normalized text for date/time processing
        normalized_text = normalize_datetime_input(user_text)
        print(f"Date-normalized text: {normalized_text}")
        
        # Try advanced intelligent date parsing first
        start_dt_obj, end_dt_obj = intelligent_date_parse(normalized_text)
        
        if start_dt_obj and end_dt_obj:
            # Convert to ISO format strings
            start_dt = start_dt_obj.isoformat()
            end_dt = end_dt_obj.isoformat()
            print(f"Intelligent parser result: start={start_dt}, end={end_dt}")
        else:
            # If intelligent parsing failed, try AI-based cleaner
            ai_response = ai_clean_datetime(normalized_text)
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
                start_dt, end_dt = parse_event_time(normalized_text)

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
        
        # Extract meeting title/description if available
        meeting_description = extract_meeting_description(original_text)
        
        # Create a descriptive meeting title
        if meeting_description:
            meeting_title = f"Meeting: {meeting_description}"
        else:
            meeting_title = f"Meeting: {original_text.strip()[:50]}"
        
        # Add meeting type to title if specified
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
        
        # Schedule the event with the extracted modifiers
        event_link = schedule_google_event(
            meeting_title, 
            start_dt, 
            end_dt,
            modifiers
        )
        
        # Format start time more nicely for the response
        start_time_local = start_time.strftime("%A, %B %d at %I:%M %p")
        
        # Enhanced response with meeting details
        reply = f"Meeting scheduled for {start_time_local} "
        reply += f"with a duration of {int(duration_hours)} hour{'s' if duration_hours != 1 else ''}!"
        
        # Add meeting type details
        if 'meeting_type' in modifiers:
            meeting_type = modifiers['meeting_type']
            if meeting_type == 'call':
                reply += " Conference call details will be sent to participants."
            elif meeting_type == 'video':
                reply += " Video conference link is included in the calendar invitation."
            elif meeting_type == 'in_person':
                reply += " Meeting will be held in person at the office."
                
        # Add attendee information if available
        if 'attendees' in modifiers:
            reply += f" Attendees: {modifiers['attendees']}."
            
        # Add link to the event
        reply += f" Event link: {event_link}"
        
        return {"reply": reply}
        
    elif "send_email" in classification_text or (req.dialog_context and req.dialog_context.get("waiting_for") in ["recipient_email", "sender_name"]):
        # Check if we're in dialog mode and need more info
        if req.dialog_context and req.dialog_context.get("waiting_for"):
            dialog_context = req.dialog_context
            
            # If we're waiting for recipient email
            if dialog_context.get("waiting_for") == "recipient_email":
                # User provided email in response to our question
                to_email = original_text.strip()
                email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
                is_valid_email = bool(re.match(email_pattern, to_email))
                
                if is_valid_email:
                    leftover_instructions = dialog_context.get("original_instructions", "")
                    explicit_subject = dialog_context.get("explicit_subject")
                    sender_name = dialog_context.get("sender_name")
                    
                    # If we already have the sender name, proceed with sending
                    if sender_name:
                        # Generate and send email with complete information
                        subject, body = generate_email_content(
                            leftover_instructions, 
                            explicit_subject, 
                            sender_name=sender_name, 
                            recipient_email=to_email
                        )
                        
                        # Send the email
                        result = send_gmail(to_email, subject, body)
                        
                        if result:
                            return {"reply": f"Email sent to {to_email} with subject: '{subject}'.\nSigned as: {sender_name}"}
                        else:
                            return {"reply": f"Failed to send email to {to_email}."}
                    else:
                        # Move to next stage - ask for sender name
                        return {
                            "reply": f"Who should I say this email is from?",
                            "dialog_context": {
                                "waiting_for": "sender_name",
                                "to_email": to_email,
                                "original_instructions": leftover_instructions,
                                "explicit_subject": explicit_subject
                            }
                        }
                else:
                    # Invalid email, ask again
                    return {
                        "reply": "That doesn't look like a valid email address. Please provide a valid email (e.g., someone@example.com):",
                        "dialog_context": dialog_context
                    }
            
            # If we're waiting for sender name
            elif dialog_context.get("waiting_for") == "sender_name":
                # Extract sender name, handling "from Name" format
                sender_text = original_text.strip()
                if sender_text.lower().startswith("from "):
                    sender_name = sender_text[5:].strip()  # Remove "from " prefix
                else:
                    sender_name = sender_text
                
                to_email = dialog_context.get("to_email")
                leftover_instructions = dialog_context.get("original_instructions", "")
                explicit_subject = dialog_context.get("explicit_subject")
                
                print(f"Generating email from {sender_name} to {to_email} with instructions: {leftover_instructions}")
                
                # Generate and send email with complete information
                subject, body = generate_email_content(
                    leftover_instructions, 
                    explicit_subject, 
                    sender_name=sender_name, 
                    recipient_email=to_email
                )
                
                # Send the email
                result = send_gmail(to_email, subject, body)
                
                if result:
                    return {"reply": f"Email sent to {to_email} with subject: '{subject}'.\nSigned as: {sender_name}"}
                else:
                    return {"reply": f"Failed to send email to {to_email}."}
        
        # Start of a new email request
        else:
            # Extract email, message instructions, explicit subject, and sender name
            to_email, leftover_instructions, explicit_subject, sender_name = extract_email_and_message(original_text)
            
            # Check if email is actually a valid address
            email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
            is_valid_email = bool(re.match(email_pattern, to_email))
            
            # If we have both valid email and sender, send immediately
            if is_valid_email and sender_name:
                print(f"Generating email from {sender_name} to {to_email} with instructions: {leftover_instructions}")
                
                # Generate and send email with complete information
                subject, body = generate_email_content(
                    leftover_instructions, 
                    explicit_subject, 
                    sender_name=sender_name, 
                    recipient_email=to_email
                )
                
                # Send the email
                result = send_gmail(to_email, subject, body)
                
                if result:
                    return {"reply": f"Email sent to {to_email} with subject: '{subject}'.\nSigned as: {sender_name}"}
                else:
                    return {"reply": f"Failed to send email to {to_email}."}
            
            # If email is missing or invalid, ask for it
            elif to_email == "someone@example.com" or not is_valid_email:
                return {
                    "reply": "Who would you like to send this email to? Please provide their email address:",
                    "dialog_context": {
                        "waiting_for": "recipient_email",
                        "original_instructions": leftover_instructions,
                        "explicit_subject": explicit_subject,
                        "sender_name": sender_name
                    }
                }
            
            # If we have a valid email but need sender info
            else:
                return {
                    "reply": f"Who should I say this email is from?",
                    "dialog_context": {
                        "waiting_for": "sender_name",
                        "to_email": to_email,
                        "original_instructions": leftover_instructions,
                        "explicit_subject": explicit_subject
                    }
                }
        
    elif "send_slack" in classification_text or "slack_send" in classification_text:
        # Extract slack channel and message with enhanced logic
        channel, text, is_ai_generated = extract_slack_channel_and_message(original_text)
        
        # Check for quoted messages
        is_quoted = bool(re.search(r'["\'](.*?)["\']', original_text))
        
        # Send the message
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
        # Extract parameters with our intelligent parameter extractor
        channel, count, search_term = extract_slack_retrieve_params(original_text)
        
        try:
            # Attempt to get messages with all parameters
            messages = get_latest_slack_messages(channel, count, search_term)
        except TypeError:
            # Fall back to just channel and count if search_term is not supported
            try:
                messages = get_latest_slack_messages(channel, count)
                
                # Add note if search was requested but not applied
                if search_term:
                    search_note = f"\n\nNote: Message filtering by content '{search_term}' is not yet implemented."
            except TypeError:
                # Final fallback to just channel if count is not supported
                messages = get_latest_slack_messages(channel)
        
        # Format them for display
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
            
            # Try to format timestamp if available
            time_str = ""
            if timestamp:
                try:
                    from datetime import datetime
                    msg_time = datetime.fromtimestamp(float(timestamp))
                    time_str = f" ({msg_time.strftime('%m/%d %I:%M %p')})"
                except:
                    pass
            
            # Format message nicely with emojis
            reply_str += f"👤 **{user}**{time_str}:\n{text}\n\n"
            
        # Add note if search was requested but not fully applied
        if search_term and 'search_note' in locals():
            reply_str += search_note
        
        return {"reply": reply_str}
    
    elif "retrieve_email" in classification_text:
        # Try to extract email count
        count = 5  # Default
        count_match = re.search(r'(last|recent|top)\s+(\d+)', user_text)
        if count_match:
            try:
                count = int(count_match.group(2))
                count = min(max(count, 1), 20)  # Clamp between 1-20
            except:
                pass
                
        # Extract sender filter (email or name)
        sender_filter = None
        
        # Check for email address pattern first
        email_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}'
        email_match = re.search(email_pattern, user_text)
        if email_match:
            sender_filter = email_match.group(0)
        else:
            # Use more inclusive name pattern that allows non-ASCII characters
            name_pattern = r'[\w\s\'\-\.]+'
            
            # Check for "from [name]" pattern
            from_name_match = re.search(f'from\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE)
            if from_name_match:
                sender_filter = from_name_match.group(1).strip()
            
            # Check for "by [name]" pattern
            elif re.search(f'by\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE):
                by_match = re.search(f'by\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE)
                sender_filter = by_match.group(1).strip()
                
            # Check for "sent by [name]" pattern
            elif re.search(f'sent\\s+by\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE):
                sent_match = re.search(f'sent\\s+by\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE)
                sender_filter = sent_match.group(1).strip()
                
            # Check for emails with a specific name pattern (without from/by)
            elif re.search(f'(?:emails?|messages?)\\s+(?:with|containing|from)\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE):
                name_match = re.search(f'(?:emails?|messages?)\\s+(?:with|containing|from)\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE)
                sender_filter = name_match.group(1).strip()
                
            # Catch "show me emails from [name]" pattern
            elif re.search(f'show\\s+(?:me\\s+)?(?:emails?|messages?)\\s+from\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE):
                show_match = re.search(f'show\\s+(?:me\\s+)?(?:emails?|messages?)\\s+from\\s+({name_pattern})(?:\\s|$|\\.|\\?|,)', user_text, re.IGNORECASE)
                sender_filter = show_match.group(1).strip()
                
        # Safety check - limit name length to prevent issues
        if sender_filter and len(sender_filter) > 50:
            sender_filter = sender_filter[:50]
        
        # Extract subject filter (for future use)
        subject_filter = None
        subject_match = re.search(r'(?:with|about|containing|subject)\s+["\']?([^"\']+)["\']?', user_text)
        if subject_match:
            subject_filter = subject_match.group(1)
        
        # Call the updated function with the sender filter
        emails_summary = get_latest_emails(count, sender_filter)
        
        # Add a note if only subject filter was requested but not applied
        if subject_filter and sender_filter is None and "No emails found" not in emails_summary:
            filter_note = f"\n\nNote: Email filtering by subject ('{subject_filter}') is not yet implemented."
            emails_summary += filter_note

        if not emails_summary:
            return {"reply": "No emails found or an error occurred."}

        return {"reply": emails_summary}
    
    elif "retrieve_crm" in classification_text or "hubspot_retrieve" in classification_text:
        # Try to extract contact count
        count = 5  # Default
        count_match = re.search(r'(last|recent|top)\s+(\d+)', user_text)
        if count_match:
            try:
                count = int(count_match.group(2))
                count = min(max(count, 1), 20)  # Clamp between 1-20
            except:
                pass
                
        # Check for contact search terms
        search_term = None
        name_match = re.search(r'(?:named|called|with name)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)', user_text)
        if name_match:
            search_term = name_match.group(1)
        
        try:
            # Try with search parameter
            contacts = get_hubspot_contacts(limit=count, search=search_term)
        except TypeError:
            # Fall back to just limit if search is not supported
            contacts = get_hubspot_contacts(limit=count)
            
            # Note if search was requested but not applied
            if search_term:
                search_note = f"\n\nNote: Contact filtering by name '{search_term}' is not yet implemented."
        
        if not contacts:
            return {"reply": "No HubSpot contacts found or an error occurred."}

        reply_str = f"📇 Here are your top {count} HubSpot contacts"
        if search_term:
            reply_str += f" matching '{search_term}'"
        reply_str += ":\n"
        
        for i, c in enumerate(contacts, start=1):
            reply_str += (
                f"\n{i}) 🧑 {c['firstname']} {c['lastname']}\n"
                f"    📧 {c['email']}\n"
                f"    🆔 ID: {c['id']}\n"
            )
            
        # Add note if search was requested but not applied
        if search_term and 'search_note' in locals():
            reply_str += search_note
            
        return {"reply": reply_str}
    
    elif "create_crm" in classification_text:
        # parse the user text for first name, last name, email
        # e.g. "create a HubSpot contact named John Doe with email john@doe.com"
        # We'll do a quick naive approach:
        fn_match = re.search(r'named\s+([A-Za-z]+)', user_text)
        ln_match = re.search(r'(?:last\s+name|surname|family\s+name)\s+([A-Za-z]+)', user_text)
        email_match = re.search(r'(?:email\s*(?:is|:)?\s*)(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b)', user_text)
        firstname = fn_match.group(1) if fn_match else "Unknown"
        lastname = ln_match.group(1) if ln_match else ""
        email = email_match.group(1) if email_match else "unknown@example.com"

        new_id = create_hubspot_contact(firstname, lastname, email)
        if new_id:
            return {"reply": f"Created new HubSpot contact with ID: {new_id}"}
        else:
            return {"reply": "Failed to create new HubSpot contact."}

    elif "update_crm" in classification_text:
        # parse ID and new fields
        id_match = re.search(r'(?:id\s+)(\d+)', user_text)
        if not id_match:
            return {"reply": "I couldn't find an ID in your request. Use e.g. 'update crm contact with id 123'."}
        contact_id = id_match.group(1)

        # parse new name or email
        fn_match = re.search(r'first\s+name\s+([A-Za-z]+)', user_text)
        ln_match = re.search(r'last\s+name\s+([A-Za-z]+)', user_text)
        email_match = re.search(r'email\s+(\S+@\S+\.\S+)', user_text)
        firstname = fn_match.group(1) if fn_match else None
        lastname = ln_match.group(1) if ln_match else None
        new_email = email_match.group(1) if email_match else None

        print(f"Parsed contact - Firstname: {firstname}, Lastname: {lastname}, Email: {email}")
        updated_id = update_hubspot_contact(contact_id, firstname, lastname, new_email)
        if updated_id:
            return {"reply": f"Updated HubSpot contact {updated_id} successfully."}
        else:
            return {"reply": f"Failed to update contact with ID {contact_id}."}


    else:
        # 'general' => enhanced GPT conversation
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
    """
    Extract a meaningful meeting description/title from the user's text.
    """
    # Try to find explicit description
    about_match = re.search(r'(?:about|regarding|concerning|for|on)\s+([^.,!?]+)', text, re.IGNORECASE)
    if about_match:
        return about_match.group(1).strip()
        
    # Try to extract anything after certain phrases
    with_match = re.search(r'(?:with|to discuss|to talk about)\s+([^.,!?]+)', text, re.IGNORECASE)
    if with_match:
        return with_match.group(1).strip()
    
    return None

def extract_slack_retrieve_params(user_text):
    """
    Extract parameters for retrieving Slack messages from user text.
    Returns (channel, count, search_term)
    """
    from server.nlp_datetime_cleaner import normalize_text
    
    # Normalize text
    normalized = normalize_text(user_text)
    
    # Default parameters
    channel = "#general"
    count = 5
    search_term = None
    
    # Extract channel
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
                # Skip if it's a common word
                common_words = ['slack', 'message', 'channel', 'messages', 'history', 'conversation', 'chat', 'all']
                if channel_name.lower() not in common_words:
                    channel = f"#{channel_name}"
            else:
                channel = channel_name
            break
            
    # Extract count
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
                # Reasonable limits
                count = min(max(count, 1), 20)
                break
            except:
                pass
    
    # Extract search term
    search_patterns = [
        r'(?:containing|with|about|mentioning|related to|that mention|that has|having)\s+["\']?([^"\'.,!?]+)["\']?',
        r'search\s+for\s+["\']?([^"\'.,!?]+)["\']?'
    ]
    
    for pattern in search_patterns:
        match = re.search(pattern, normalized)
        if match:
            search_term = match.group(1).strip()
            if search_term:  # Only use non-empty
                break
    
    return channel, count, search_term
