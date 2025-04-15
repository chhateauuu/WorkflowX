from transformers import pipeline
import re
import dateparser
from datetime import datetime, timedelta
import pytz

date_rewrite_pipeline = pipeline("text2text-generation", model="google/flan-t5-base")

def normalize_text(text: str) -> str:
    """
    General purpose text normalizer that corrects common typos,
    standardizes formats, and prepares text for further processing.
    Works for all intents, not just date/time.
    """
    if not text:
        return ""
        
    # Convert to lowercase
    normalized = text.lower()
    
    # Fix common typos for all intents
    typo_corrections = {
        # General typos
        r'\bnex\b': 'next',
        r'\bwoth\b': 'with',
        r'\bfro\b': 'for',
        r'\bwiht\b': 'with',
        r'\bfomr\b': 'from',
        r'\bteh\b': 'the',
        r'\babuot\b': 'about',
        r'\bqucik\b': 'quick',
        r'\bscheduel\b': 'schedule',
        r'\bshcedule\b': 'schedule',
        r'\bmeeting\b': 'meeting',
        r'\bmeetinf\b': 'meeting',
        r'\bmeetin\b': 'meeting',
        r'\bschedul\b': 'schedule',
        r'\bschdul\b': 'schedule',
        r'\bemial\b': 'email',
        r'\bemail\b': 'email',
        r'\bemil\b': 'email',
        r'\bsned\b': 'send',
        r'\bsed\b': 'send',
        r'\bsendd\b': 'send',
        r'\bsalck\b': 'slack',
        r'\bslak\b': 'slack',
        r'\bslck\b': 'slack',
        r'\bmesage\b': 'message',
        r'\bmessg\b': 'message',
        r'\bmsg\b': 'message',
        r'\bretreive\b': 'retrieve',
        r'\bretreve\b': 'retrieve',
        r'\bretriev\b': 'retrieve',
        r'\breatrieve\b': 'retrieve',
        r'\bretrve\b': 'retrieve',
        r'\bconacts\b': 'contacts',
        r'\bcontcts\b': 'contacts',
        r'\bcontact\b': 'contacts',
        r'\btonigt\b': 'tonight',
        r'\btomoro\b': 'tomorrow',
        r'\btomorow\b': 'tomorrow',
        r'\btmrw\b': 'tomorrow',
        r'\btmr\b': 'tomorrow',
        r'\btoday\b': 'today',
        r'\btdy\b': 'today',
        r'\byesterdy\b': 'yesterday',
        r'\byestday\b': 'yesterday',
        r'\byest\b': 'yesterday',
        r'\bmonday\b': 'monday',
        r'\bmon\b': 'monday',
        r'\btuesday\b': 'tuesday',
        r'\btue\b': 'tuesday',
        r'\btues\b': 'tuesday',
        r'\bwednesday\b': 'wednesday',
        r'\bwed\b': 'wednesday',
        r'\bthursday\b': 'thursday',
        r'\bthu\b': 'thursday',
        r'\bthur\b': 'thursday',
        r'\bthurs\b': 'thursday',
        r'\bfriday\b': 'friday',
        r'\bfri\b': 'friday',
        r'\bsaturday\b': 'saturday',
        r'\bsat\b': 'saturday',
        r'\bsunday\b': 'sunday',
        r'\bsun\b': 'sunday',
    }
    
    # Apply all typo corrections
    for pattern, replacement in typo_corrections.items():
        normalized = re.sub(pattern, replacement, normalized)
    
    # Standardize time formats
    normalized = re.sub(r'(\d{1,2})pm', r'\1 pm', normalized)
    normalized = re.sub(r'(\d{1,2})am', r'\1 am', normalized)
    normalized = re.sub(r'(\d{1,2}):(\d{2})pm', r'\1:\2 pm', normalized)
    normalized = re.sub(r'(\d{1,2}):(\d{2})am', r'\1:\2 am', normalized)
    
    # Standardize date phrases
    normalized = re.sub(r'next\s+weeks?', 'next week', normalized)
    normalized = re.sub(r'(\d+)\s*h(\s|$)', r'\1 hour\2', normalized)
    normalized = re.sub(r'(\d+)\s*hr(\s|$)', r'\1 hour\2', normalized)
    normalized = re.sub(r'(\d+)\s*hrs(\s|$)', r'\1 hours\2', normalized)
    normalized = re.sub(r'(\d+)\s*min(\s|$)', r'\1 minute\2', normalized)
    normalized = re.sub(r'(\d+)\s*m(\s|$)', r'\1 minute\2', normalized)
    normalized = re.sub(r'(\d+)\s*mins(\s|$)', r'\1 minutes\2', normalized)
    
    # Standardize email related phrases
    normalized = re.sub(r'send\s+mail', 'send email', normalized)
    normalized = re.sub(r'send\s+a\s+mail', 'send email', normalized)
    normalized = re.sub(r'send\s+a\s+email', 'send email', normalized)
    normalized = re.sub(r'send\s+out\s+an?\s+email', 'send email', normalized)
    
    # Standardize slack related phrases
    normalized = re.sub(r'send\s+a\s+slack', 'send slack', normalized)
    normalized = re.sub(r'send\s+a\s+slack\s+message', 'send slack', normalized)
    normalized = re.sub(r'post\s+to\s+slack', 'send slack', normalized)
    normalized = re.sub(r'post\s+on\s+slack', 'send slack', normalized)
    normalized = re.sub(r'slack\s+message', 'send slack', normalized)
    
    # Prevent duplication of "send" for slack messages
    normalized = re.sub(r'send\s+send\s+slack', 'send slack', normalized)
    normalized = re.sub(r'send\s+msg', 'send message', normalized)
    normalized = re.sub(r'send\s+a\s+msg', 'send message', normalized)
    
    # Standardize slack message recognition with additional patterns
    normalized = re.sub(r'slack\s+msg', 'send slack', normalized)
    normalized = re.sub(r'message\s+on\s+slack', 'send slack', normalized)
    normalized = re.sub(r'message\s+in\s+slack', 'send slack', normalized)
    
    # Standardize retrieval phrases
    normalized = re.sub(r'get\s+emails?', 'retrieve email', normalized)
    normalized = re.sub(r'check\s+emails?', 'retrieve email', normalized)
    normalized = re.sub(r'show\s+me\s+emails?', 'retrieve email', normalized)
    normalized = re.sub(r'get\s+slack\s+messages?', 'retrieve slack', normalized)
    normalized = re.sub(r'check\s+slack', 'retrieve slack', normalized)
    normalized = re.sub(r'show\s+me\s+slack\s+messages?', 'retrieve slack', normalized)
    normalized = re.sub(r'get\s+contacts?', 'retrieve crm', normalized)
    normalized = re.sub(r'show\s+me\s+contacts?', 'retrieve crm', normalized)
    normalized = re.sub(r'get\s+hubspot\s+contacts?', 'retrieve crm', normalized)
    normalized = re.sub(r'show\s+hubspot\s+contacts?', 'retrieve crm', normalized)
    
    return normalized.strip()

def intelligent_date_parse(text):
    """
    Uses dateparser library to intelligently parse dates from natural language.
    Returns a tuple of (start_datetime, end_datetime) or (None, None) if parsing fails.
    """
    # First, try to extract time expressions
    
    # Get timezone for consistent datetime handling
    local_tz = pytz.timezone("America/Indiana/Indianapolis")
    now = datetime.now(local_tz)
    
    # Define common regex patterns
    time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?'
    day_of_week_pattern = r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday)'
    month_pattern = r'(january|february|march|april|may|june|july|august|september|october|november|december)'
    day_of_month_pattern = r'(\d{1,2})(?:st|nd|rd|th)?'
    
    # Extract duration
    duration_hours = 1  # Default duration
    duration_patterns = [
        r'for\s+(\d+)\s*hours?',
        r'for\s+(\d+)\s*h',
        r'(\d+)\s*hours?\s+long',
        r'(\d+)\s*hour\s+meeting',
        r'(\d+)\s*h\s+meeting',
        r'for\s+(\d+)\s*hr',
        r'for\s+(\d+)\s*hrs',
    ]
    
    for pattern in duration_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                duration_hours = int(match.group(1))
                break
            except:
                pass
    
    # Pattern list from most specific to most general
    date_patterns = [
        # Pattern: "next week Tuesday at 3pm"
        {
            'regex': r'next\s+week\s+' + day_of_week_pattern + r'\s+at\s+' + time_pattern,
            'handler': lambda m: parse_next_week_day_at_time(m, now, local_tz)
        },
        # Pattern: "next Monday at 2pm"
        {
            'regex': r'next\s+' + day_of_week_pattern + r'\s+at\s+' + time_pattern,
            'handler': lambda m: parse_next_day_at_time(m, now, local_tz)
        },
        # Pattern: "Tuesday next week at 2pm"
        {
            'regex': day_of_week_pattern + r'\s+next\s+week\s+at\s+' + time_pattern,
            'handler': lambda m: parse_day_next_week_at_time(m, now, local_tz)
        },
        # Pattern: "tomorrow at 3pm"
        {
            'regex': r'tomorrow\s+at\s+' + time_pattern,
            'handler': lambda m: parse_tomorrow_at_time(m, now, local_tz)
        },
        # Pattern: "today at 4pm"
        {
            'regex': r'today\s+at\s+' + time_pattern,
            'handler': lambda m: parse_today_at_time(m, now, local_tz)
        },
        # Pattern: "March 15 at 2pm" 
        {
            'regex': month_pattern + r'\s+' + day_of_month_pattern + r'\s+at\s+' + time_pattern,
            'handler': lambda m: parse_month_day_at_time(m, now, local_tz)
        },
        # Pattern: "15th March at 2pm"
        {
            'regex': day_of_month_pattern + r'\s+(?:of\s+)?' + month_pattern + r'\s+at\s+' + time_pattern,
            'handler': lambda m: parse_day_month_at_time(m, now, local_tz)
        },
        # Pattern: "in 3 days at 2pm"
        {
            'regex': r'in\s+(\d+)\s+days?\s+at\s+' + time_pattern,
            'handler': lambda m: parse_in_days_at_time(m, now, local_tz)
        },
        # Pattern: "next month on the 15th at 2pm"
        {
            'regex': r'next\s+month\s+(?:on\s+)?(?:the\s+)?' + day_of_month_pattern + r'\s+at\s+' + time_pattern,
            'handler': lambda m: parse_next_month_day_at_time(m, now, local_tz)
        },
        # Fallback pattern
        {
            'regex': r'at\s+' + time_pattern,
            'handler': lambda m: parse_time_only(m, now, local_tz)
        }
    ]
    
    # Try all patterns
    for pattern in date_patterns:
        match = re.search(pattern['regex'], text, re.IGNORECASE)
        if match:
            start_dt = pattern['handler'](match)
            if start_dt:
                end_dt = start_dt + timedelta(hours=duration_hours)
                return start_dt, end_dt
    
    # Try dateparser as last resort
    try:
        # Extract time if present
        time_match = re.search(r'at\s+' + time_pattern, text, re.IGNORECASE)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            am_pm = time_match.group(3)
            
            # Adjust hour for PM
            if am_pm and ('pm' in am_pm.lower() or 'p.m' in am_pm.lower()) and hour < 12:
                hour += 12
            elif am_pm and ('am' in am_pm.lower() or 'a.m' in am_pm.lower()) and hour == 12:
                hour = 0
                
            # Remove time part to help dateparser
            date_text = re.sub(r'at\s+' + time_pattern, '', text)
            
            # Special handling for specific date patterns like "April 2"
            month_day_match = re.search(
                r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?',
                date_text,
                re.IGNORECASE
            )
            
            if month_day_match:
                # We have a specific month and day
                month_name = month_day_match.group(1).lower()
                day = int(month_day_match.group(2))
                
                month_map = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                
                month = month_map[month_name]
                year = now.year
                
                # If the date is in the past, use next year
                if (month < now.month) or (month == now.month and day < now.day):
                    year += 1
                
                # Create naive datetime and localize it
                naive_dt = datetime(year, month, day, hour, minute, 0, 0)
                start_dt = local_tz.localize(naive_dt)
                end_dt = start_dt + timedelta(hours=duration_hours)
                return start_dt, end_dt
            
            # Try dateparser on the remaining text
            date_settings = {'RETURN_AS_TIMEZONE_AWARE': True, 'TIMEZONE': local_tz}
            parsed_date = dateparser.parse(date_text, settings=date_settings)
            
            if parsed_date:
                # Create a naive datetime based on parsed date but with our exact hour/minute
                naive_dt = datetime(
                    parsed_date.year,
                    parsed_date.month,
                    parsed_date.day,
                    hour,
                    minute,
                    0,
                    0
                )
                # Properly localize it
                start_dt = local_tz.localize(naive_dt)
                end_dt = start_dt + timedelta(hours=duration_hours)
                return start_dt, end_dt
        
        # No explicit time found, try full text
        date_settings = {'RETURN_AS_TIMEZONE_AWARE': True, 'TIMEZONE': local_tz}
        parsed_date = dateparser.parse(text, settings=date_settings)
        
        if parsed_date:
            if time_match is None:
                # Default to 3pm if no time specified, using naive datetime first
                naive_dt = datetime(
                    parsed_date.year,
                    parsed_date.month,
                    parsed_date.day,
                    15,  # 3 PM
                    0,
                    0,
                    0
                )
                # Properly localize it
                start_dt = local_tz.localize(naive_dt)
            else:
                start_dt = parsed_date
                
            end_dt = start_dt + timedelta(hours=duration_hours)
            return start_dt, end_dt
    except Exception as e:
        print(f"Error in dateparser: {e}")
    
    # No date/time could be parsed
    return None, None

# Helper functions for date parsing
def parse_next_week_day_at_time(match, now, local_tz):
    weekday_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
    weekday = match.group(1).lower()
    hour = int(match.group(2))
    minute = int(match.group(3) or 0)
    am_pm = match.group(4)
    
    # Adjust hour for PM
    if am_pm and ('pm' in am_pm.lower() or 'p.m' in am_pm.lower()) and hour < 12:
        hour += 12
    elif am_pm and ('am' in am_pm.lower() or 'a.m' in am_pm.lower()) and hour == 12:
        hour = 0
    
    # Calculate days to next week's day
    target_weekday = weekday_map[weekday]
    current_weekday = now.weekday()
    days_to_add = (target_weekday - current_weekday) % 7
    
    # Add 7 more days to get to next week
    days_to_add += 7
    
    target_date = now + timedelta(days=days_to_add)
    
    # Create a naive datetime with the specified hour and minute
    naive_dt = datetime(
        target_date.year, 
        target_date.month, 
        target_date.day, 
        hour, 
        minute, 
        0, 
        0
    )
    
    # Localize the naive datetime to the target timezone
    return local_tz.localize(naive_dt)

def parse_next_day_at_time(match, now, local_tz):
    weekday_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
    weekday = match.group(1).lower()
    hour = int(match.group(2))
    minute = int(match.group(3) or 0)
    am_pm = match.group(4)
    
    # Adjust hour for PM
    if am_pm and ('pm' in am_pm.lower() or 'p.m' in am_pm.lower()) and hour < 12:
        hour += 12
    elif am_pm and ('am' in am_pm.lower() or 'a.m' in am_pm.lower()) and hour == 12:
        hour = 0
    
    # Calculate days to next occurrence of the day
    target_weekday = weekday_map[weekday]
    current_weekday = now.weekday()
    days_to_add = (target_weekday - current_weekday) % 7
    if days_to_add == 0:
        days_to_add = 7  # Next week's same day
    
    target_date = now + timedelta(days=days_to_add)
    
    # Create a naive datetime with the specified hour and minute
    naive_dt = datetime(
        target_date.year, 
        target_date.month, 
        target_date.day, 
        hour, 
        minute, 
        0, 
        0
    )
    
    # Localize the naive datetime to the target timezone
    return local_tz.localize(naive_dt)

def parse_day_next_week_at_time(match, now, local_tz):
    weekday_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
    weekday = match.group(1).lower()
    hour = int(match.group(2))
    minute = int(match.group(3) or 0)
    am_pm = match.group(4)
    
    # Adjust hour for PM
    if am_pm and ('pm' in am_pm.lower() or 'p.m' in am_pm.lower()) and hour < 12:
        hour += 12
    elif am_pm and ('am' in am_pm.lower() or 'a.m' in am_pm.lower()) and hour == 12:
        hour = 0
    
    # Calculate days to specified day next week
    target_weekday = weekday_map[weekday]
    current_weekday = now.weekday()
    
    # Days until that day of next week
    days_to_add = (target_weekday - current_weekday) % 7
    
    # Add 7 more days to get to next week
    days_to_add += 7
    
    target_date = now + timedelta(days=days_to_add)
    
    # Create a naive datetime with the specified hour and minute
    naive_dt = datetime(
        target_date.year, 
        target_date.month, 
        target_date.day, 
        hour, 
        minute, 
        0, 
        0
    )
    
    # Localize the naive datetime to the target timezone
    return local_tz.localize(naive_dt)

def parse_tomorrow_at_time(match, now, local_tz):
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    am_pm = match.group(3)
    
    # Adjust hour for PM
    if am_pm and ('pm' in am_pm.lower() or 'p.m' in am_pm.lower()) and hour < 12:
        hour += 12
    elif am_pm and ('am' in am_pm.lower() or 'a.m' in am_pm.lower()) and hour == 12:
        hour = 0
    
    tomorrow = now + timedelta(days=1)
    
    # Create a naive datetime with the specified hour and minute
    naive_dt = datetime(
        tomorrow.year, 
        tomorrow.month, 
        tomorrow.day, 
        hour, 
        minute, 
        0, 
        0
    )
    
    # Localize the naive datetime to the target timezone
    return local_tz.localize(naive_dt)

def parse_today_at_time(match, now, local_tz):
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    am_pm = match.group(3)
    
    # Adjust hour for PM
    if am_pm and ('pm' in am_pm.lower() or 'p.m' in am_pm.lower()) and hour < 12:
        hour += 12
    elif am_pm and ('am' in am_pm.lower() or 'a.m' in am_pm.lower()) and hour == 12:
        hour = 0
    
    # Create a naive datetime with the specified hour and minute
    naive_dt = datetime(
        now.year, 
        now.month, 
        now.day, 
        hour, 
        minute, 
        0, 
        0
    )
    
    # Localize the naive datetime to the target timezone
    return local_tz.localize(naive_dt)

def parse_month_day_at_time(match, now, local_tz):
    month_map = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    month_name = match.group(1).lower()
    day = int(match.group(2))
    hour = int(match.group(3))
    minute = int(match.group(4) or 0)
    am_pm = match.group(5)
    
    # Adjust hour for PM
    if am_pm and ('pm' in am_pm.lower() or 'p.m' in am_pm.lower()) and hour < 12:
        hour += 12
    elif am_pm and ('am' in am_pm.lower() or 'a.m' in am_pm.lower()) and hour == 12:
        hour = 0
    
    month = month_map[month_name]
    
    # Determine year
    year = now.year
    # If the month & day combo is in the past, use next year
    if (month < now.month) or (month == now.month and day < now.day):
        year += 1
    
    try:
        # Create a naive datetime first
        naive_dt = datetime(year, month, day, hour, minute, 0, 0)
        # Then localize it to the target timezone
        return local_tz.localize(naive_dt)
    except:
        # Handle invalid dates (e.g., Feb 30)
        return None

def parse_day_month_at_time(match, now, local_tz):
    month_map = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    day = int(match.group(1))
    month_name = match.group(2).lower()
    hour = int(match.group(3))
    minute = int(match.group(4) or 0)
    am_pm = match.group(5)
    
    # Adjust hour for PM
    if am_pm and ('pm' in am_pm.lower() or 'p.m' in am_pm.lower()) and hour < 12:
        hour += 12
    elif am_pm and ('am' in am_pm.lower() or 'a.m' in am_pm.lower()) and hour == 12:
        hour = 0
    
    month = month_map[month_name]
    
    # Determine year
    year = now.year
    # If the month & day combo is in the past, use next year
    if (month < now.month) or (month == now.month and day < now.day):
        year += 1
    
    try:
        # Create a naive datetime first
        naive_dt = datetime(year, month, day, hour, minute, 0, 0)
        # Then localize it to the target timezone
        return local_tz.localize(naive_dt)
    except:
        # Handle invalid dates (e.g., Feb 30)
        return None

def parse_in_days_at_time(match, now, local_tz):
    days = int(match.group(1))
    hour = int(match.group(2))
    minute = int(match.group(3) or 0)
    am_pm = match.group(4)
    
    # Adjust hour for PM
    if am_pm and ('pm' in am_pm.lower() or 'p.m' in am_pm.lower()) and hour < 12:
        hour += 12
    elif am_pm and ('am' in am_pm.lower() or 'a.m' in am_pm.lower()) and hour == 12:
        hour = 0
    
    target_date = now + timedelta(days=days)
    
    # Create a naive datetime with the specified hour and minute
    naive_dt = datetime(
        target_date.year, 
        target_date.month, 
        target_date.day, 
        hour, 
        minute, 
        0, 
        0
    )
    
    # Localize the naive datetime to the target timezone
    return local_tz.localize(naive_dt)

def parse_next_month_day_at_time(match, now, local_tz):
    day = int(match.group(1))
    hour = int(match.group(2))
    minute = int(match.group(3) or 0)
    am_pm = match.group(4)
    
    # Adjust hour for PM
    if am_pm and ('pm' in am_pm.lower() or 'p.m' in am_pm.lower()) and hour < 12:
        hour += 12
    elif am_pm and ('am' in am_pm.lower() or 'a.m' in am_pm.lower()) and hour == 12:
        hour = 0
    
    # Calculate next month
    month = now.month + 1
    year = now.year
    
    if month > 12:
        month = 1
        year += 1
    
    try:
        # Create a naive datetime with the specified hour and minute
        naive_dt = datetime(year, month, day, hour, minute, 0, 0)
        
        # Localize the naive datetime to the target timezone
        return local_tz.localize(naive_dt)
    except:
        # Handle invalid dates (e.g., Feb 30)
        return None

def parse_time_only(match, now, local_tz):
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    am_pm = match.group(3)
    
    # Adjust hour for PM
    if am_pm and ('pm' in am_pm.lower() or 'p.m' in am_pm.lower()) and hour < 12:
        hour += 12
    elif am_pm and ('am' in am_pm.lower() or 'a.m' in am_pm.lower()) and hour == 12:
        hour = 0
    
    # Create a naive datetime with the specified hour and minute
    naive_dt = datetime(
        now.year, 
        now.month, 
        now.day, 
        hour, 
        minute, 
        0, 
        0
    )
    
    # Localize the naive datetime to the target timezone
    localized_dt = local_tz.localize(naive_dt)
    
    # If the time is earlier than current time, assume tomorrow
    if localized_dt < now:
        localized_dt = localized_dt + timedelta(days=1)
    
    return localized_dt

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

def extract_intent_modifiers(text, intent):
    """
    Extract modifiers specific to different intents from complex sentences.
    This handles context-specific qualifiers, adverbs, and other parameters.
    
    Returns a dictionary of extracted modifiers relevant to the intent.
    """
    modifiers = {}
    
    if intent == "schedule_meeting":
        # Extract meeting importance/priority
        priority_match = re.search(r'(?:high|important|urgent|critical|priority|essential)', text, re.IGNORECASE)
        if priority_match:
            modifiers['priority'] = 'high'
            
        # Extract meeting type
        type_matches = {
            'call': r'(?:call|phone|conference|audio)',
            'video': r'(?:video|zoom|teams|webex|google meet)',
            'in_person': r'(?:in[- ]person|face[- ]to[- ]face|onsite|on[- ]site|in the office)',
            'interview': r'(?:interview|screening|candidate)',
            '1on1': r'(?:1[ -]on[ -]1|one[ -]on[ -]one|individual|personal)'
        }
        
        for meeting_type, pattern in type_matches.items():
            if re.search(pattern, text, re.IGNORECASE):
                modifiers['meeting_type'] = meeting_type
                break
                
        # Extract attendees
        attendees_match = re.search(r'with\s+([A-Za-z\s,]+)(?:and|,)?', text, re.IGNORECASE)
        if attendees_match:
            attendees = attendees_match.group(1).strip()
            # Clean up the text
            attendees = re.sub(r'(?:and|,)+', ',', attendees)
            modifiers['attendees'] = attendees
    
    elif intent == "send_email":
        # Extract email priority
        priority_match = re.search(r'(?:high|important|urgent|critical|priority)', text, re.IGNORECASE)
        if priority_match:
            modifiers['priority'] = 'high'
            
        # Extract email formality
        formality_matches = {
            'formal': r'(?:formal|professional|official|business)',
            'casual': r'(?:casual|informal|friendly|relaxed)',
            'concise': r'(?:brief|concise|short|quick)'
        }
        
        for formality, pattern in formality_matches.items():
            if re.search(pattern, text, re.IGNORECASE):
                modifiers['formality'] = formality
                break
        
        # Extract CC recipients
        cc_match = re.search(r'cc\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})', text, re.IGNORECASE)
        if cc_match:
            modifiers['cc'] = cc_match.group(1)
    
    elif intent == "send_slack" or intent == "retrieve_slack":
        # Extract message visibility
        visibility_match = re.search(r'(private|direct|dm)', text, re.IGNORECASE)
        if visibility_match:
            modifiers['private'] = True
    
    elif intent == "retrieve_email" or intent == "retrieve_crm":
        # Extract sorting preference
        sort_matches = {
            'newest': r'(?:newest|latest|recent)',
            'oldest': r'(?:oldest|earliest)'
        }
        
        for sort_order, pattern in sort_matches.items():
            if re.search(pattern, text, re.IGNORECASE):
                modifiers['sort'] = sort_order
                break
                
        # Extract detail level
        detail_matches = {
            'summary': r'(?:summary|brief|overview)',
            'detailed': r'(?:detailed|full|complete|all details)'
        }
        
        for detail_level, pattern in detail_matches.items():
            if re.search(pattern, text, re.IGNORECASE):
                modifiers['detail'] = detail_level
                break
    
    return modifiers