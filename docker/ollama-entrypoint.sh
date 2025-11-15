#!/bin/sh

ollama serve &
PID=$!

trap 'kill "$PID"' INT TERM

echo "Waiting for Ollama to be available..."

i=0
while [ "$i" -lt 30 ]; do
  if ollama list >/dev/null 2>&1; then
    break
  fi
  sleep 2
  i=$((i + 1))
done

if ! ollama list | grep -q "mistral"; then
  echo "Pulling model mistral:7b..."
  ollama pull mistral:7b || true
fi

wait "$PID"

