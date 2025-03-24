import os
import base64
import datetime
import openai

from email.mime.text import MIMEText
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .gmail_auth import get_gmail_credentials

###############################################################################
# 1) SEND EMAIL (unchanged from your current version)
###############################################################################
def send_gmail(to_email: str, subject: str, body: str):
    """
    Sends an email via the user's personal Gmail account using OAuth tokens.
    """
    try:
        creds = get_gmail_credentials()
        service = build("gmail", "v1", credentials=creds)

        # Build the MIME message
        message = MIMEText(body)
        message["to"] = to_email
        message["subject"] = subject

        # Encode the message in base64
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        raw_body = {"raw": raw}

        # Send the message
        sent_msg = service.users().messages().send(
            userId="me", body=raw_body
        ).execute()

        return sent_msg  # Returns JSON with keys like 'id', 'labelIds', etc.

    except HttpError as e:
        print(f"Gmail send error: {e}")
        return None

###############################################################################
# 2) HELPER: Extract plain-text body from "full" format
###############################################################################
def _extract_plain_text(msg_payload: dict) -> str:
    """
    Given the 'payload' field from a Gmail message in 'full' format,
    attempts to find and decode the plain-text body.
    """
    import base64

    # If multipart, search parts
    if "parts" in msg_payload:
        for part in msg_payload["parts"]:
            mime_type = part.get("mimeType", "")
            if mime_type == "text/plain":
                data = part["body"].get("data", "")
                if data:
                    decoded = base64.urlsafe_b64decode(data)
                    return decoded.decode("utf-8", errors="replace")
        # fallback if no text/plain found
    else:
        # single-part message
        data = msg_payload.get("body", {}).get("data", "")
        if data:
            decoded = base64.urlsafe_b64decode(data)
            return decoded.decode("utf-8", errors="replace")

    return ""  # if not found

###############################################################################
# 3) HELPER: Summarize an email's body with GPT
###############################################################################
def _summarize_email(content: str) -> str:
    """
    Uses GPT to summarize the email content into a short paragraph.
    """
    if not content.strip():
        return "No content to summarize."

    prompt = (
        "Please summarize the following email content in a concise manner, "
        "highlighting any key points. If there's a sender or date mentioned, "
        "please include them as well:\n\n"
        f"{content}"
    )

    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful AI that summarizes emails."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=150,
            temperature=0.7,
        )
        summary = response.choices[0].message.content.strip()
        return summary
    except Exception as e:
        print(f"OpenAI summarization error: {e}")
        return "Summary unavailable."

###############################################################################
# 4) GET + SUMMARIZE LATEST EMAILS FROM INBOX
###############################################################################
def get_latest_emails(max_results: int = 5) -> str:
    """
    Retrieves the latest messages from the user's Inbox (max_results),
    then for each email:
      - Extracts From, Date, Subject, plain-text body
      - Summarizes the content using GPT
    Returns a nicely formatted string with details for all emails.
    """
    try:
        creds = get_gmail_credentials()
        service = build("gmail", "v1", credentials=creds)

        # 1) List messages in the inbox
        result = service.users().messages().list(
            userId="me",
            q="in:inbox",
            maxResults=max_results
        ).execute()

        messages = result.get("messages", [])
        if not messages:
            return "No emails found in your Inbox."

        final_output = ["📬 Here are your latest emails:\n\n"]

        # 2) For each message ID, get the 'full' format
        for idx, msg_info in enumerate(messages, start=1):
            msg_id = msg_info["id"]
            msg_data = service.users().messages().get(
                userId="me",
                id=msg_id,
                format="full"
            ).execute()

            payload = msg_data.get("payload", {})
            headers = payload.get("headers", [])

            # Extract basic headers: "From", "Date", "Subject"
            from_ = next((h["value"] for h in headers if h["name"].lower() == "from"), "(Unknown Sender)")
            date_ = next((h["value"] for h in headers if h["name"].lower() == "date"), "(Unknown Date)")
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "(No Subject)")

            # 3) Extract plain-text body
            plain_text = _extract_plain_text(payload)

            # 4) Summarize with GPT
            summary = _summarize_email(plain_text)

            # 5) Format
            email_info = (
                f"Email #{idx}\n"
                f"Subject: {subject}\n"
                f"From: {from_}\n"
                f"Date: {date_}\n"
                f"Summary: {summary}\n"
                f"----------------------------------------\n\n"
            )

            final_output.append(email_info)

        return "\n".join(final_output)

    except HttpError as e:
        print(f"Gmail retrieve error: {e}")
        return "Error retrieving emails."

