from transformers import pipeline
import re
import dateparser
from datetime import datetime, timedelta

date_rewrite_pipeline = pipeline("text2text-generation", model="google/flan-t5-base")

def intelligent_date_parse(text):
    """
    Uses dateparser library to intelligently parse dates from natural language.
    Returns a tuple of (start_datetime, end_datetime) or (None, None) if parsing fails.
    """
    # First, try to extract time expressions
    # Patterns like "next week Wednesday at 2pm"
    weekday_next_week = re.search(r'next week\s+(?:on\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text, re.IGNORECASE)
    
    # Pattern "next Wednesday at 2pm"
    next_weekday = re.search(r'next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text, re.IGNORECASE)
    
    # Pattern "Wednesday next week at 2pm"
    weekday_next_week_alt = re.search(r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+next week\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text, re.IGNORECASE)
    
    # Extract duration
    duration_match = re.search(r'for\s+(\d+)\s*hours?', text, re.IGNORECASE)
    duration_hours = int(duration_match.group(1)) if duration_match else 1  # Default 1 hour
    
    # Parse based on pattern matched
    if weekday_next_week:
        day_name = weekday_next_week.group(1)
        hour = int(weekday_next_week.group(2))
        minute = int(weekday_next_week.group(3) or 0)
        am_pm = weekday_next_week.group(4) or ''
        
        # Adjust for PM
        if am_pm.lower() == 'pm' and hour < 12:
            hour += 12
        
        # Get next week's weekday
        date_str = f"next {day_name} {hour}:{minute}"
        start_dt = dateparser.parse(date_str)
        
    elif next_weekday:
        day_name = next_weekday.group(1)
        hour = int(next_weekday.group(2))
        minute = int(next_weekday.group(3) or 0)
        am_pm = next_weekday.group(4) or ''
        
        # Adjust for PM
        if am_pm.lower() == 'pm' and hour < 12:
            hour += 12
        
        date_str = f"next {day_name} {hour}:{minute}"
        start_dt = dateparser.parse(date_str)
        
    elif weekday_next_week_alt:
        day_name = weekday_next_week_alt.group(1)
        hour = int(weekday_next_week_alt.group(2))
        minute = int(weekday_next_week_alt.group(3) or 0)
        am_pm = weekday_next_week_alt.group(4) or ''
        
        # Adjust for PM
        if am_pm.lower() == 'pm' and hour < 12:
            hour += 12
            
        date_str = f"next {day_name} {hour}:{minute}"
        start_dt = dateparser.parse(date_str)
    
    else:
        # Try generic dateparser as fallback
        try:
            # Try to find time mention
            time_match = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text, re.IGNORECASE)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                am_pm = time_match.group(3) or ''
                
                # Adjust for PM
                if am_pm.lower() == 'pm' and hour < 12:
                    hour += 12
                
                # Remove time part to help dateparser parse the date
                date_text = re.sub(r'at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?', '', text)
                date_text = date_text.strip()
                
                # Parse date without time
                date_only = dateparser.parse(date_text)
                if date_only:
                    # Combine date with our extracted time
                    start_dt = date_only.replace(hour=hour, minute=minute)
                else:
                    start_dt = None
            else:
                # No specific time found, let dateparser handle everything
                start_dt = dateparser.parse(text)
        except:
            start_dt = None
    
    if start_dt:
        end_dt = start_dt + timedelta(hours=duration_hours)
        return start_dt, end_dt
    else:
        return None, None

def ai_clean_datetime(user_text: str) -> str:
    """
    Attempts to rewrite ambiguous datetime phrases into a clearer format.
    Returns a string with START and END datetime in ISO format.
    """
    prompt = (
        "You are a smart assistant that extracts date and time information from natural language.\n"
        "For the given input, extract the meeting date and time.\n"
        "Format your response as: START=YYYY-MM-DDThh:mm END=YYYY-MM-DDThh:mm\n\n"
        "Examples:\n"
        "Input: Schedule a meeting for next Wednesday at 3 pm\n"
        "Output: START=2023-06-07T15:00 END=2023-06-07T16:00\n\n"
        "Input: Schedule a meeting for tomorrow at 10am for 2 hours\n"
        "Output: START=2023-05-31T10:00 END=2023-05-31T12:00\n\n"
        "Input: Schedule a meeting next week on Wednesday at 2pm\n"
        "Output: START=2023-06-07T14:00 END=2023-06-07T15:00\n\n"
        f"Input: {user_text}\n"
        "Output:"
    )

    try:
        response = date_rewrite_pipeline(prompt, max_length=100, do_sample=False)[0]["generated_text"]
        return response.strip()
    except Exception as e:
        print(f"Error in AI date cleaning: {e}")
        return ""

def normalize_datetime_input(user_text: str) -> str:
    text = user_text.lower()

    # Fix common typos
    text = re.sub(r'\bnex\b', 'next', text)
    text = re.sub(r'\bmeetinf\b', 'meeting', text)
    text = re.sub(r'\bmeetin\b', 'meeting', text)
    
    # Handle "for next week" or "next week" patterns
    text = re.sub(r'for next week', 'next week', text)
    
    # Handle patterns like "next week at X on [weekday]" -> "next [weekday] at X"
    text = re.sub(r'next week at (\d{1,2}(?::\d{2})?\s*(?:am|pm)?) on (monday|tuesday|wednesday|thursday|friday|saturday|sunday)', 
                 r'next \2 at \1', text)
    
    # Handle patterns like "next week on [weekday] at X" -> "next [weekday] at X"
    text = re.sub(r'next week on (monday|tuesday|wednesday|thursday|friday|saturday|sunday) at (\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', 
                 r'next \1 at \2', text)
    
    # Handle patterns like "next week on wednesday"
    text = re.sub(r'next week (on )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', r'next \2', text)
    
    # Handle "on wednesday next week" → "next wednesday"
    text = re.sub(r'on (monday|tuesday|wednesday|thursday|friday|saturday|sunday) next week', r'next \1', text)
    
    # Handle patterns without explicit "next" but where we can infer it
    text = re.sub(r'for (monday|tuesday|wednesday|thursday|friday|saturday|sunday) at', r'for next \1 at', text)
    
    # Standardize time formats
    text = re.sub(r'(\d{1,2})pm', r'\1 pm', text)
    text = re.sub(r'(\d{1,2})am', r'\1 am', text)

    return text