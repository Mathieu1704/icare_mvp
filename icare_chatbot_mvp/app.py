"""FastAPI chatbot service with LLM‑based intent extraction (no regex).

The service listens on /chat and answers questions about sensor connectivity
based on data stored in MongoDB.  It relies on a local Llama‑compatible model
(served via llama‑cpp) to identify the user intent and the target company.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from llama_cpp import Llama
from pydantic import BaseModel
from pymongo import MongoClient, errors

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "icare")
JOURS_SEUIL = int(os.getenv("JOURS_SEUIL", "2"))
MODEL_PATH = os.getenv("MODEL_PATH", "models/mistral-7b-instruct.gguf")
MODEL_CTX = int(os.getenv("MODEL_CTX", "4096"))

# ---------------------------------------------------------------------------
# MongoDB connection (fail fast on startup)
# ---------------------------------------------------------------------------

try:
    mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5_000)
    mongo_client.admin.command("ping")
except errors.ServerSelectionTimeoutError as exc:
    raise RuntimeError(f"MongoDB not reachable: {exc}") from exc

db = mongo_client[DB_NAME]

# ---------------------------------------------------------------------------
# LLM setup (llama‑cpp)
# ---------------------------------------------------------------------------

try:
    llm = Llama(model_path=MODEL_PATH, n_ctx=MODEL_CTX)
except Exception as exc:  # pragma: no cover – model loading errors displayed at boot
    raise RuntimeError(f"Unable to load model at '{MODEL_PATH}': {exc}") from exc

SYSTEM_PROMPT = (
    "You are an extraction agent that converts a user request about IoT sensors "
    "into a JSON payload.  Supported JSON schema:"\n
    "{"\n  ""intent"": string,   // one of 'check_connectivity', 'list_disconnected', 'unknown'"\n  ""company"": string|null // company name mentioned by the user"\n}"\n"
    "\nReturn ONLY the JSON, without additional text."
)

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    locale: str | None = "fr"  # "fr" or "en"

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def extract_intent(raw_message: str) -> Dict[str, Any]:
    """Run the LLM to extract intent & company. Returns a dict or raises HTTPException."""

    prompt = (
        f"<s>[INST] <<SYS>>\n{SYSTEM_PROMPT}\n<</SYS>>\n\n"  # system context
        f"{raw_message}\n[/INST]"  # user message
    )

    try:
        result = llm(prompt, max_tokens=256, temperature=0.0, stop=["</s>"])
        raw_json = result["choices"][0]["text"].strip()
        payload = json.loads(raw_json)
    except Exception as exc:  # parsing or model failure
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse LLM output: {exc}; output was: {raw_json[:200]}...",
        ) from exc

    # minimal validation
    if not isinstance(payload, dict):
        raise HTTPException(422, "Invalid payload structure returned by LLM")

    intent = payload.get("intent", "unknown")
    if intent not in {"check_connectivity", "list_disconnected", "unknown"}:
        intent = "unknown"
    payload["intent"] = intent
    return payload


def get_site_status(entreprise: str, jours_seuil: int = JOURS_SEUIL) -> Dict[str, Any]:
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

    agg = list(db.capteurs.aggregate(pipeline, maxTimeMS=1_000))
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

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(title="Icare Chatbot MVP", version="0.2.0 (LLM)")


@app.post("/chat")
async def chat(req: ChatRequest):
    # 1) Ask the LLM to understand the request
    extraction = extract_intent(req.message.strip())
    intent = extraction.get("intent", "unknown")
    company = extraction.get("company") or "icare_mons"  # fallback for MVP

    # 2) Gather data from MongoDB (only if intent needs it)
    if intent in {"check_connectivity", "list_disconnected"}:
        status = get_site_status(company)
    else:
        status = {}

    # 3) Craft the answer (minimal logic, will improve later)
    if intent == "check_connectivity":
        if status["disconnected"] == 0:
            answer_fr = "Oui, tous les capteurs sont connectés."
            answer_en = "Yes, all sensors are connected."
        else:
            answer_fr = f"Non, {status['disconnected']} capteurs sont déconnectés."
            answer_en = f"No, {status['disconnected']} sensors are disconnected."

    elif intent == "list_disconnected":
        if status["disconnected"] == 0:
            answer_fr = "Aucun capteur n'est déconnecté."
            answer_en = "No disconnected sensors."
        else:
            list_str = ", ".join(status["disconnected_list"][:10])
            answer_fr = f"Capteurs déconnectés : {list_str}"
            answer_en = f"Disconnected sensors: {list_str}"

    else:  # unknown intent — ask user to reformulate
        answer_fr = (
            "Je n'ai pas compris la question. Essayez par ex. : 'Tous les capteurs sont-ils connectés ?'"
        )
        answer_en = (
            "I didn't understand the question. Try for instance: 'Are all sensors connected?'"
        )

    return {"answer": answer_fr if req.locale == "fr" else answer_en}
