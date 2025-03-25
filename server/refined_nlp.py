# refined_nlp.py
from transformers import pipeline

# We use a zero-shot pipeline with 'facebook/bart-large-mnli'
# which can classify any text given a set of candidate labels.
zero_shot_classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

def bert_classify(user_text: str):
    """
    Classifies user_text into one of our known intents using zero-shot classification.
    Returns a string like 'schedule_meeting', 'send_email', etc.
    """
    candidate_labels = [
        "schedule_meeting",
        "send_email",
        "retrieve_email",
        "retrieve_slack",
        "retrieve_crm",
        "general"
    ]
    
    result = zero_shot_classifier(user_text, candidate_labels)
    # result looks like:
    # {
    #   'sequence': 'user_text...',
    #   'labels': ['some_label', 'another_label', ...],
    #   'scores': [0.95, 0.02, ...]
    # }
    
    top_label = result["labels"][0]
    # e.g. "schedule_meeting"
    return top_label.lower()
