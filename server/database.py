# server/database.py

import motor.motor_asyncio
from beanie import init_beanie
import os
from dotenv import load_dotenv

from server.models import User  # we'll create this soon

load_dotenv()

MONGO_DETAILS = os.getenv("MONGO_DETAILS")

client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_DETAILS)
db = client.get_default_database()  # default is from the connection string db name

async def init_db():
    await init_beanie(database=db, document_models=[User])
