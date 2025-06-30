from pymongo import MongoClient

def insert_test_data():
    client = MongoClient("mongodb://localhost:27017/")
    db = client["i_see_test"]
    collection = db["capteurs"]
    collection.delete_many({})  # Vide la collection

    capteurs = [
        {
            "id_capteur": "c1",
            "entreprise": "icare_mons",
            "type": "vibration",
            "batterie": 88,
            "connecte": True,
            "gateway_id": "g1"
        },
        {
            "id_capteur": "c2",
            "entreprise": "icare_mons",
            "type": "ultrason",
            "batterie": 75,
            "connecte": True,
            "gateway_id": "g1"
        },
        {
            "id_capteur": "c3",
            "entreprise": "icare_mons",
            "type": "temperature",
            "batterie": 15,
            "connecte": False,
            "gateway_id": "g2"
        },
        {
            "id_capteur": "c4",
            "entreprise": "icare_liege",
            "type": "vibration",
            "batterie": 60,
            "connecte": True,
            "gateway_id": "g3"
        }
    ]

    collection.insert_many(capteurs)
    print("✅ Données de test insérées.")

if __name__ == "__main__":
    insert_test_data()