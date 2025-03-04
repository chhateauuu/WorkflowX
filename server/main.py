import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

origins = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def root():
    return {"message": "Hello from WorkflowX API!"}

@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    user_text = req.message

    # 1) First, ask GPT to classify the request
    # You define the system message to instruct GPT how to respond
    classification_response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a classifier. "
                    "Classify the user's message into one of these intents: "
                    "schedule_meeting, send_email, retrieve_data, or general. "
                    "Output ONLY the intent name."
                )
            },
            {
                "role": "user",
                "content": user_text
            }
        ],
        max_tokens=5,
        temperature=0.0,  # We want consistent, deterministic classification
    )

    # 2) Parse the classification
    classification_text = classification_response.choices[0].message.content.strip().lower()

    # 3) Branch logic based on classification
    if "schedule_meeting" in classification_text:
        # Potentially do your scheduling logic or placeholder
        return {"reply": "Intent recognized: schedule_meeting. [Placeholder scheduling logic]"}

    elif "send_email" in classification_text:
        return {"reply": "Intent recognized: send_email. [Placeholder email logic]"}

    elif "retrieve_data" in classification_text:
        return {"reply": "Intent recognized: retrieve_data. [Placeholder data retrieval logic]"}

    else:
        # 'general' or unrecognized => do a normal GPT response
        # Another call to GPT for an actual AI conversation
        final_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant for WorkflowX."
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ],
            max_tokens=100,
            temperature=0.7,
        )
        ai_text = final_response.choices[0].message.content.strip()
        return {"reply": ai_text}
