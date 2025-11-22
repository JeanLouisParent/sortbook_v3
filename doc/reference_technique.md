# Référence Technique

Ce document détaille les aspects techniques de Sortbook v3 : arguments CLI, architecture du code, et variables d'environnement.

## 1. Interface en Ligne de Commande (CLI)

Le script principal `src/epub_metadata.py` accepte les arguments suivants :

| Argument | Type | Description |
| :--- | :--- | :--- |
| `--folder PATH` | Chemin | Dossier racine contenant les EPUBs à traiter. |
| `--limit N` | Entier | Nombre maximum de fichiers à traiter (utile pour tester). |
| `--test` | Flag | Utilise le webhook de test n8n et affiche la réponse brute. |

## 2. Architecture du Code

### Structure des Fichiers
- `src/epub_metadata.py` : Point d'entrée unique contenant toute la logique.
- `src/__init__.py` : Marqueur de package Python.

### Classes Principales
- **`Config`** : Charge la configuration depuis les variables d'environnement et les arguments CLI.
- **`EpubMetadata`** : Stocke les métadonnées extraites du fichier OPF (Dublin Core).
- **`EpubResult`** : Stocke le résultat normalisé provenant de n8n (titre, auteur, explication).

### Flux de Traitement (`process_epub`)
1. **Extraction** : Lecture du fichier ZIP (EPUB), extraction du texte (`extract_text_from_epub`) et des métadonnées OPF (`extract_metadata_from_epub`).
2. **Appel n8n** : Envoi d'un payload JSON au webhook configuré (`call_n8n`).
3. **Normalisation** : Conversion de la réponse n8n en `EpubResult`.
4. **Logging** : Écriture du résultat dans le fichier JSONL.

## 3. Variables d'Environnement

| Variable | Description | Défaut |
| :--- | :--- | :--- |
| `EPUB_ROOT` | Chemin hôte vers les ebooks (utilisé par Docker). | `./data/ebooks` |
| `EPUB_SOURCE_DIR` | Chemin conteneur vers les ebooks. | `/data` |
| `EPUB_DEST` | Chemin hôte vers la destination (info log). | `./data/ebooks_sorted` |
| `LOG_DIR` | Dossier des logs. | `./log` |
| `EPUB_LOG_FILE` | Nom du fichier de log. | `n8n_response.json` |
| `N8N_WEBHOOK_PROD_URL` | URL du webhook (Prod). | - |
| `N8N_WEBHOOK_TEST_URL` | URL du webhook (Test). | - |
| `N8N_VERIFY_SSL` | Vérification SSL (`true`/`false`/path). | `true` |
| `N8N_TIMEOUT` | Timeout requête HTTP (secondes). | `120.0` |
| `DEFAULT_MAX_TEXT_CHARS` | Max caractères extraits. | `4000` |

## 4. Format des Données

### Payload envoyé à n8n
```json
{
  "filename": "livre.epub",
  "isbn": "978-3-16-148410-0",
  "root": "/data",
  "destination": "/data/sorted",
  "text": "Début du texte extrait...",
  "pages_raw": ["<html>...</html>"],
  "metadata": {
    "title": "Titre OPF",
    "creator": "Auteur OPF",
    ...
  }
}
```

### Réponse normalisée (interne)
Le script normalise les réponses de n8n pour obtenir cet objet :
```python
EpubResult(
    titre="Titre Validé",
    auteur="Auteur Validé",
    explication="Raison..."
)
```
