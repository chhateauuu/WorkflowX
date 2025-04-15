# refined_nlp.py
from transformers import pipeline
import re
import openai
import os

# We use a zero-shot pipeline with 'facebook/bart-large-mnli'
# which can classify any text given a set of candidate labels.
zero_shot_classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

# Get API key from environment
api_key = os.getenv("OPENAI_API_KEY")
if api_key:
    openai.api_key = api_key

def bert_classify(user_text: str):
    """
    Classifies user_text into one of our known intents using zero-shot classification.
    Returns a string like 'schedule_meeting', 'send_email', etc.
    Also uses common pattern detection for reliability.
    """
    # First try pattern-based classification for common, reliable patterns
    pattern_intents = {
        'schedule_meeting': [
            r'schedule\s+(?:a\s+)?(?:new\s+)?(?:meeting|appointment|event|call)',
            r'set\s+up\s+(?:a\s+)?(?:meeting|appointment|event|call)',
            r'book\s+(?:a\s+)?(?:meeting|appointment|slot|time)',
            r'calendar\s+(?:meeting|appointment|event)',
            r'plan\s+(?:a\s+)?(?:meeting|appointment|event|call)',
            r'next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)'
        ],
        'create_crm': [
            r'create\s+(?:a\s+)?(?:hubspot|crm)\s+(?:contact|record)',
            r'add\s+(?:a\s+)?(?:hubspot|crm)\s+contact'
        ],
        'update_crm': [
            r'update\s+(?:hubspot|crm)\s+(?:contact|record)\s+(?:with\s+id|id\s+)\s+(\d+)',
            r'modify\s+(?:a\s+)?(?:hubspot|crm)\s+contact'
        ],
        'send_email': [
            r'send\s+(?:a\s+)?(?:email|mail|message)',
            r'write\s+(?:a\s+)?(?:email|mail|message|note)',
            r'compose\s+(?:a\s+)?(?:email|mail|message)',
            r'draft\s+(?:a\s+)?(?:email|mail|message)',
            r'email\s+to\s+',
            r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}'  # Email address in text
        ],
        'send_slack': [
            r'send\s+(?:a\s+)?(?:slack|channel)\s+(?:message|note|update)',
            r'post\s+(?:a\s+)?(?:message|note|update)\s+(?:to|on|in)\s+(?:slack|channel)',
            r'slack\s+(?:message|note|update)',
            r'message\s+(?:to|on|in)\s+(?:#[\w-]+)',
            r'post\s+(?:to|on|in)\s+(?:#[\w-]+)'
        ],
        'retrieve_slack': [
            r'get\s+(?:slack|channel)\s+(?:messages?|history|conversation)',
            r'check\s+(?:slack|channel)\s+(?:messages?|history|conversation)',
            r'show\s+(?:me\s+)?(?:slack|channel)\s+(?:messages?|history|conversation)',
            r'retrieve\s+(?:slack|channel)\s+(?:messages?|history|conversation)',
            r'read\s+(?:slack|channel)\s+(?:messages?|history|conversation)'
        ],
        'retrieve_email': [
            r'get\s+(?:my\s+)?(?:emails?|mails?|inbox)',
            r'check\s+(?:my\s+)?(?:emails?|mails?|inbox)',
            r'show\s+(?:me\s+)?(?:my\s+)?(?:emails?|mails?|inbox)',
            r'read\s+(?:my\s+)?(?:emails?|mails?|inbox)',
            r'fetch\s+(?:my\s+)?(?:emails?|mails?|inbox)'
        ],
        'retrieve_crm': [
            r'get\s+(?:crm|hubspot|customer|contacts?)',
            r'show\s+(?:me\s+)?(?:crm|hubspot|customer|contacts?)',
            r'retrieve\s+(?:crm|hubspot|customer|contacts?)',
            r'fetch\s+(?:crm|hubspot|customer|contacts?)',
            r'find\s+(?:crm|hubspot|customer|contacts?)'
        ]
        
        
    }
    
    # Try to match patterns first
    user_text_lower = user_text.lower()
    for intent, patterns in pattern_intents.items():
        for pattern in patterns:
            if re.search(pattern, user_text_lower):
                return intent
    
    # Fall back to the transformers-based zero-shot classification
    candidate_labels = [
        "schedule_meeting",
        "create_crm",
        "update_crm",
        "send_email",
        "retrieve_email",
        "retrieve_slack",
        "send_slack", 
        "retrieve_crm",
        "general"
    ]
    
    try:
        result = zero_shot_classifier(user_text, candidate_labels)
        top_label = result["labels"][0]
        top_score = result["scores"][0]
        
        # Only return if confidence is reasonable
        if top_score > 0.5:
            return top_label.lower()
    except Exception as e:
        print(f"Error in BERT classification: {e}")
    
    # If BERT classification fails or has low confidence, try GPT
    try:
        if api_key:
            # Use GPT as a backup classifier
            gpt_resp = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a classifier. Classify the user's message into "
                            "one of these intents: schedule_meeting, send_email, retrieve_email, "
                            "send_slack, retrieve_slack, retrieve_crm or general. "
                            "Output ONLY the intent name, nothing else."
                        )
                    },
                    {"role": "user", "content": user_text}
                ],
                max_tokens=10,
                temperature=0.0,
            )
            gpt_intent = gpt_resp.choices[0].message.content.strip().lower()
            
            # Validate the response is one of our intents
            valid_intents = set(candidate_labels)
            if gpt_intent in valid_intents:
                return gpt_intent
    except Exception as e:
        print(f"Error in GPT classification: {e}")
    
    # Default to general
    return "general"
