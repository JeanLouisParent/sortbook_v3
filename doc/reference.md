# Référence technique

## Arguments CLI

- `--folder PATH` : dossier racine contenant les EPUB.
- `--confidence-min FLOAT` : seuil minimal (0.0 à 1.0, défaut issu de `CONFIDENCE_MIN`).
- `--dry-run` : simulation (aucun renommage écrit sur disque).
- `--test` : utilise le webhook de test et affiche la réponse brute.
- `--limit N` : nombre maximal de fichiers à traiter.

## Fonctions principales (src/epub_metadata.py)

- `extract_text_from_epub(epub_path: Path, max_chars: int = 4000) -> str`
  - Ouvre l’EPUB, priorise certaines pages (cover, titlepage…), supprime balises HTML, renvoie un extrait limité.

- `extract_metadata_from_epub(epub_path: Path) -> dict`
  - Parse le fichier OPF interne (si présent) et renvoie un dict avec: `title`, `creator`, `publisher`, `language`, `identifier`, `description`.

- `call_n8n(payload: dict, *, test_mode: bool = False) -> dict | None`
  - Envoie `payload` au webhook n8n.
  - En mode test (`test_mode=True`): affiche le statut + réponse brute (`resp.text`) et renvoie `None`.
  - En mode normal: parse la réponse JSON et normalise plusieurs formats:
    - dict déjà normalisé: `{titre, auteur, confiance, explication}`;
    - liste avec `output`: `[{"output": {...}}]`;
    - liste simple: `[{"title": "...", "author": "..."}]` → remappé vers `titre`/`auteur`.

- `process_epub(epub_path: Path, dry_run: bool = True, confidence_min: str = "moyenne", *, test_mode: bool = False) -> None`
  - Construit le payload, appelle n8n, affiche le résultat, journalise systématiquement.
  - En mode normal: si `titre != "inconnu"` et `confiance >= threshold`, propose/écrit le renommage.
  - En mode test: s’arrête après l’appel n8n (affichage brut), pas d’analyse/renommage.

- `process_folder(folder, dry_run=True, confidence_min="moyenne", limit=None, *, test_mode=False) -> None`
  - Itère sur les fichiers `.epub` (récursif), appelle `process_epub`.
  - Respecte `--limit` si fourni.

## Variables d’environnement

- `N8N_WEBHOOK_TEST_URL` / `N8N_WEBHOOK_PROD_URL` : URLs de test et de prod.
- `N8N_VERIFY_SSL` : `false` pour désactiver, ou chemin vers une CA/bundle.
- `N8N_TIMEOUT` : délai max en secondes (défaut 120).
- `EPUB_SOURCE_DIR` : chemin source (pour exécution en conteneur).
- `EPUB_DEST` : destination logique (utilisée dans le payload et les logs).
- `LOG_DIR` / `EPUB_LOG_FILE` : emplacement et nom du fichier log JSONL.
- `CONFIDENCE_MIN` : seuil par défaut si non fourni via CLI.

