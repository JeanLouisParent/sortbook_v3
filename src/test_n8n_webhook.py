#!/usr/bin/env python3
"""Script de test rapide pour envoyer un texte fixe au webhook n8n."""

import os
import sys

import requests

DEFAULT_WEBHOOK_URL = "http://localhost:5678/webhook/epub-metadata"
WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", DEFAULT_WEBHOOK_URL)
TEST_TEXT = os.environ.get("N8N_TEST_TEXT", "test")


def main() -> None:
    print(f"Envoi d'un test au webhook : {WEBHOOK_URL}")
    try:
        response = requests.post(WEBHOOK_URL, json={"text": TEST_TEXT}, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Erreur lors de l'appel webhook : {exc}")
        sys.exit(1)

    try:
        data = response.json()
    except ValueError:
        print("Réponse non JSON :")
        print(response.text)
        sys.exit(1)

    print("Réponse JSON reçue :")
    for key, value in data.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
