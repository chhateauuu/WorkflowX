# server/hubspot_integration.py

import os
import requests
from dotenv import load_dotenv

load_dotenv()

HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN")

def get_hubspot_contacts(limit=5):
    """
    Retrieves the latest 'limit' contacts from HubSpot.
    Returns a list of dicts with relevant info (e.g. email, firstname, lastname).
    """
    url = f"https://api.hubapi.com/crm/v3/objects/contacts?limit={limit}"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"HubSpot error {response.status_code}: {response.text}")
            return []
        
        data = response.json()
        results = data.get("results", [])
        contacts_list = []
        for contact in results:
            props = contact.get("properties", {})
            contacts_list.append({
                "id": contact.get("id"),
                "email": props.get("email"),
                "firstname": props.get("firstname"),
                "lastname": props.get("lastname"),
            })
        return contacts_list
    except Exception as e:
        print(f"Error calling HubSpot: {e}")
        return []
