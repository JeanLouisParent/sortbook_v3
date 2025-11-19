#!/bin/sh
set -e

DB_PATH="/database/openlibrary_dumps.sqlite"

if [ ! -f "$DB_PATH" ]; then
  echo "Creating SQLite database at $DB_PATH"
  mkdir -p "$(dirname "$DB_PATH")"
  # Cette commande suffit à initialiser un fichier SQLite vide
  sqlite3 "$DB_PATH" "PRAGMA user_version = 1;"
else
  echo "SQLite database already exists at $DB_PATH, nothing to do."
fi

# Garder le conteneur vivant pour les connexions interactives
tail -f /dev/null

