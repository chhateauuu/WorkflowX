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

def create_hubspot_contact(firstname, lastname, email):
    """
    Creates a new contact in HubSpot unless one already exists with the same email.
    Returns the new (or existing) contact's ID or None if error.
    """
    # Check if contact already exists
    existing_id = find_hubspot_contact_by_email(email)
    if existing_id:
        print(f"Contact already exists with ID: {existing_id}")
        return existing_id

    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json",
    }
    body = {
        "properties": {
            "firstname": firstname,
            "lastname": lastname,
            "email": email
        }
    }
    try:
        response = requests.post(url, headers=headers, json=body)
        if response.status_code == 201:
            data = response.json()
            return data.get("id")
        else:
            print(f"HubSpot error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Error creating contact: {e}")
        return None


def update_hubspot_contact(contact_id, firstname=None, lastname=None, email=None):
    """
    Updates an existing contact in HubSpot by contact_id.
    Provide whichever fields you want to update.
    """
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json",
    }
    properties = {}
    if firstname: properties["firstname"] = firstname
    if lastname: properties["lastname"] = lastname
    if email: properties["email"] = email

    body = { "properties": properties }
    try:
        response = requests.patch(url, headers=headers, json=body)
        if response.status_code == 200:
            data = response.json()
            return data.get("id")  # or return True
        else:
            print(f"HubSpot error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Error updating contact: {e}")
        return None

def find_hubspot_contact_by_email(email):
    """
    Searches HubSpot for a contact by email. Returns the contact's ID if found, else None.
    """
    url = f"https://api.hubapi.com/crm/v3/objects/contacts/search"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json",
    }
    body = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "email",
                        "operator": "EQ",
                        "value": email
                    }
                ]
            }
        ],
        "properties": ["firstname", "lastname", "email"]
    }

    try:
        response = requests.post(url, headers=headers, json=body)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                return results[0]["id"]  # Return the first matching contact's ID
            else:
                return None
        else:
            print(f"HubSpot search error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Error searching for contact: {e}")
        return None

