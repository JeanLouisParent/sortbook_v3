#!/bin/sh
set -e
ollama serve &
PID=$!
trap 'kill $PID' INT TERM
echo "Attente de la disponibilité d'Ollama..."
for i in $(seq 1 30); do
    if ollama list >/dev/null 2>&1; then
        break
    fi
    sleep 2
done
if ! ollama list | grep -q "mistral"; then
    echo "Téléchargement du modèle mistral:7b..."
    ollama pull mistral:7b || true
fi
wait $PID
