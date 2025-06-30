Icare Chatbot MVP – direct MongoDB access
========================================

### Prérequis
* Docker ≥ 24 et plugin `docker compose`
* (Optionnel) Python 3.12 si vous voulez lancer les scripts hors conteneur.

### Démarrage rapide
```bash
# 1. Cloner (ou copier) le dépôt
$ cd icare_chatbot_mvp

# 2. Lancer l’environnement complet
$ docker compose up --build -d

# 3. Injecter un jeu de données factice
$ docker compose exec chatbot python sample_dataset.py

# 4. Tester le chatbot
$ curl -X POST http://localhost:8000/chat \
       -H "Content-Type: application/json" \
       -d '{"message":"Tous les capteurs sont-ils connectés ?"}'
```

### Structure du projet
```
.
├── Dockerfile
├── docker-compose.yml
├── app.py
├── sample_dataset.py
├── requirements.txt
└── .env.example
```
