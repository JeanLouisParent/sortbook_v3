# AGENTS: Architecture, Flux et Guidelines

## Vue d’ensemble

- Composants:
  - n8n: workflow orchestrant l’analyse sémantique (exposé via webhook HTTPS).
  - Agent Python (ce repo): lit les EPUB, extrait texte + métadonnées, appelle n8n, journalise et renomme selon la confiance.
  - Docker Compose: facilite l’orchestration (n8n, agent, Ollama en option).

## Flux de bout en bout

1) L’agent parcourt les `.epub`, extrait du texte (priorise pages titre/couverture) et lit quelques champs OPF.
2) Il envoie à n8n un payload JSON: `{ filename, root, destination, text, metadata }`.
3) n8n renvoie titre/auteur (+ éventuellement confiance/explication). En mode test, aucune structure imposée.
4) L’agent loggue systématiquement une ligne JSONL; si confiance et titre valides, il propose/écrit un renommage.

## Répartition des fichiers

- `src/epub_metadata.py` (script principal)
  - Fonctions clés:
    - `extract_text_from_epub`: texte nettoyé, limite ~4k chars.
    - `extract_metadata_from_epub`: lecture OPF (title/creator/...)
    - `call_n8n(payload, test_mode)`: POST vers le webhook; en `test_mode`, affiche la réponse brute et retourne `None`.
      - Formats gérés hors test: dict normalisé; liste avec `output`; liste simple `[{title, author}]` (remappée vers `titre/auteur`).
    - `process_epub(..., test_mode)`: prépare payload, appelle n8n, log; en mode normal, applique seuil et renommage.
    - `process_folder(..., test_mode)`: itère sur les `.epub` et appelle `process_epub`.

- `doc/usage.md`: exécution locale/Docker, TLS, variables n8n, sélection `--test`, formats de réponse, journaux.
- `doc/reference.md`: référence CLI + fonctions (signatures, comportements).
- `README.md`: aperçu, arguments principaux, .env, formats pris en charge, Docker, arborescence.

## Variables d’environnement (principales)

- `N8N_WEBHOOK_PROD_URL` / `N8N_WEBHOOK_TEST_URL`: URLs webhook.
- `N8N_VERIFY_SSL`: `false` ou chemin vers CA/bundle (ex: `/certs/n8n.crt`).
- `N8N_TIMEOUT`: timeout HTTP (s).
- `CONFIDENCE_MIN`: seuil par défaut (CLI prioritaire).
- `EPUB_SOURCE_DIR`, `EPUB_DEST`, `LOG_DIR`, `EPUB_LOG_FILE`.

## Comportement CLI

- `--test`: 
  - utilise l’URL de test (si définie),
  - affiche la réponse brute du webhook (pas d’exigence JSON),
  - n’applique aucun renommage.
- Sans `--test`: exige un JSON structuré; gère les formats listés plus haut.
- `--dry-run`: empêche les écritures (renommages simulés seulement).

## Services docker-compose

- n8n (5678): webhook HTTPS (certs montés depuis `./certs`).
- epub-agent: conteneur Python (exécute le script à la demande; monte `EPUB_ROOT` sur `/data`).
- ollama (11434, optionnel): serveur de modèles; recommandé en installation native plutôt qu’en conteneur.

## Guidelines contribution

- Changements ciblés, cohérents avec le style existant (pas de refactor cosmétique gratuit).
- Quand une interface change (CLI, formats n8n, variables), mettre à jour simultanément: `README.md`, `doc/usage.md`, `doc/reference.md`.
- Éviter d’ajouter des dépendances lourdes sans discussion.
- Tests rapides:
  - Local: `python src/epub_metadata.py --folder <path> --dry-run --limit 5`
  - Docker: `docker compose exec epub-agent python src/epub_metadata.py --dry-run --limit 10`
- Documentation: sections brèves, listes claires, exemples exécutables.
