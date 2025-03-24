# server/slack_integration.py
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()  # If you haven't already in main

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

def send_slack_message(channel: str, text: str) -> bool:
    """
    Sends a Slack message to the specified channel using your bot token.
    Returns True if successful, False otherwise.
    """
    client = WebClient(token=SLACK_BOT_TOKEN)
    try:
        response = client.chat_postMessage(channel=channel, text=text)
        # If no error raised, success
        return True
    except SlackApiError as e:
        print(f"Slack API Error: {e.response['error']}")
        return False

def get_latest_slack_messages(channel: str, limit: int = 5):
    """
    Retrieves the latest 'limit' messages from the given Slack channel.
    """
    client = WebClient(token=SLACK_BOT_TOKEN)
    try:
        response = client.conversations_history(channel=channel, limit=limit)
        return response["messages"]
    except SlackApiError as e:
        print(f"Slack API Error: {e.response['error']}")
        return []
