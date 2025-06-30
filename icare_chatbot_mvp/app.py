"""FastAPI chatbot service with direct MongoDB access."""
import os, re
from datetime import datetime, timedelta

from fastapi import FastAPI
from pydantic import BaseModel
from pymongo import MongoClient, errors
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ------------------------------------------------
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "icare")
JOURS_SEUIL = int(os.getenv("JOURS_SEUIL", "2"))

try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
except errors.ServerSelectionTimeoutError as exc:
    raise RuntimeError(f"MongoDB not reachable: {exc}")

db = client[DB_NAME]

# --- FastAPI app --------------------------------------------------
app = FastAPI(title="Icare Chatbot MVP", version="0.1.0")

# --- Models -------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    locale: str | None = "fr"  # "fr" or "en"

# --- Simple intent matching (regex) ------------------------------
REGEX_ALL_CONNECTED = re.compile(r"(?:tous|all).*?(?:capteurs|sensors).*?(?:connectés|connected)", re.I)
REGEX_LIST_DISCONNECTED = re.compile(r"(?:quels|which|liste|list).*?(?:capteurs|sensors).*?(?:déconnectés|disconnected)", re.I)

# --- Helper to query MongoDB -------------------------------------
def get_site_status(entreprise: str, jours_seuil: int = JOURS_SEUIL):
    """Return dict with connected/disconnected counts and list of disconnected sensors."""
    seuil = datetime.utcnow() - timedelta(days=jours_seuil)
    pipeline = [
        {"$match": {"entreprise": entreprise}},
        {
            "$project": {
                "_id": 0,
                "id_capteur": 1,
                "connected": {"$gt": ["$timestamp_last_data", seuil]},
            }
        },
        {
            "$group": {
                "_id": "$connected",
                "count": {"$sum": 1},
                "list": {"$push": "$id_capteur"},
            }
        },
    ]
    agg = list(db.capteurs.aggregate(pipeline, maxTimeMS=1000))
    connected = disconnected = 0
    disc_list: list[str] = []
    for doc in agg:
        if doc["_id"]:
            connected = doc["count"]
        else:
            disconnected = doc["count"]
            disc_list = doc["list"]
    return {
        "connected": connected,
        "disconnected": disconnected,
        "disconnected_list": disc_list,
    }

# --- Chat endpoint ------------------------------------------------
@app.post("/chat")
async def chat(req: ChatRequest):
    msg = req.message.strip()
    entreprise = "icare_mons"  # MVP: hard‑coded; extract from message later

    status = get_site_status(entreprise)

    # Intent: all sensors connected ?
    if REGEX_ALL_CONNECTED.search(msg):
        if status["disconnected"] == 0:
            return {
                "answer": {
                    "fr": "Oui, tous les capteurs sont connectés.",
                    "en": "Yes, all sensors are connected.",
                }[req.locale]
            }
        else:
            return {
                "answer": {
                    "fr": f"Non, {status['disconnected']} capteurs sont déconnectés.",
                    "en": f"No, {status['disconnected']} sensors are disconnected.",
                }[req.locale]
            }

    # Intent: list disconnected sensors
    if REGEX_LIST_DISCONNECTED.search(msg):
        if status["disconnected"] == 0:
            return {
                "answer": {
                    "fr": "Aucun capteur n'est déconnecté.",
                    "en": "No disconnected sensors.",
                }[req.locale]
            }
        else:
            list_str = ", ".join(status["disconnected_list"])
            return {
                "answer": {
                    "fr": f"Capteurs déconnectés : {list_str}",
                    "en": f"Disconnected sensors: {list_str}",
                }[req.locale]
            }

    # Fallback
    return {
        "answer": {
            "fr": "Je n'ai pas compris la question. Essayez par ex. : 'Tous les capteurs sont-ils connectés ?'",
            "en": "I didn't understand the question. Try for instance: 'Are all sensors connected?'",
        }[req.locale]
    }
