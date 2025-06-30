"""Génère une base de test avec des capteurs et des gateways factices."""
import random, string
from datetime import datetime, timedelta
from pymongo import MongoClient
import os, argparse, sys

TYPES = ["vibration", "temperature", "humidity", "pressure"]

def rand_id(prefix: str, length: int = 6) -> str:
    return prefix + "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_sensors(n: int, entreprise: str, gateways: list[str], pct_disconnected: float = 0.1):
    now = datetime.utcnow()
    for _ in range(n):
        last_delta = random.randint(0, 1) if random.random() > pct_disconnected else random.randint(3, 7)
        yield {
            "id_capteur": rand_id("c"),
            "entreprise": entreprise,
            "type": random.choice(TYPES),
            "batterie": random.randint(10, 100),
            "gateway_id": random.choice(gateways),
            "timestamp_last_data": now - timedelta(days=last_delta),
        }

def main():
    parser = argparse.ArgumentParser(description="Seed MongoDB with fake sensor data")
    parser.add_argument("--uri", default=os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
    parser.add_argument("--db", default=os.getenv("DB_NAME", "icare"))
    parser.add_argument("--entreprise", default="icare_mons")
    parser.add_argument("--sensors", type=int, default=200)
    args = parser.parse_args()

    client = MongoClient(args.uri)
    db = client[args.db]

    # clean collections
    db.capteurs.drop()
    db.gateways.drop()

    gateways = [rand_id("g") for _ in range(10)]
    db.gateways.insert_many({"gateway_id": g, "entreprise": args.entreprise} for g in gateways)

    db.capteurs.insert_many(generate_sensors(args.sensors, args.entreprise, gateways))
    print(f"Inserted {args.sensors} sensors and {len(gateways)} gateways into '{args.db}'.")

if __name__ == "__main__":
    sys.exit(main())
