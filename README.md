# sortbook_v3

Automatise l'identification et le renommage de fichiers EPUB via un webhook n8n.

## Aperçu
- Extrait un texte pertinent de chaque EPUB et quelques métadonnées OPF.
- Envoie un payload au webhook n8n et récupère titre/auteur (+ options).
- Renomme le fichier si la confiance est suffisante; sinon, journalise seulement.
- Deux modes d’appel du webhook:
  - `--test`: affiche la réponse brute (pas d’exigence JSON, pas de renommage).
  - normal: attend un JSON structuré et applique la logique métier.

## Installation rapide (local)

```
pip install -r requirements.txt
python src/epub_metadata.py --folder /chemin/vers/ebooks --dry-run --limit 5
```

Le script lit `N8N_WEBHOOK_*`, `EPUB_SOURCE_DIR`, `CONFIDENCE_MIN`, etc., depuis l’environnement. Passez `--no-dry-run` ou `DRY_RUN=false` pour renommer réellement.

## Arguments CLI (principaux)
- `--folder PATH` : dossier des EPUB à traiter.
- `--dry-run` : simulation, n’écrit aucun renommage.
- `--limit N` : limite le nombre d’EPUB traités.
- `--confidence-min FLOAT` : seuil de confiance (0.0 à 1.0).
- `--test` : utilise l’URL de test et affiche la réponse brute du webhook.

## Configuration (.env)
Variables lues par le script et la stack Docker:
```
EPUB_ROOT=G:/livres bruts
EPUB_SOURCE_DIR=/data
EPUB_DEST=G:/Livres_sorted
LOG_DIR=/app/log
EPUB_LOG_FILE=n8n_response.json

N8N_WEBHOOK_TEST_URL=https://192.168.1.56:5678/webhook-test/epub-metadata
N8N_WEBHOOK_PROD_URL=https://192.168.1.56:5678/webhook/epub-metadata
N8N_VERIFY_SSL=/certs/n8n.crt
N8N_TIMEOUT=180

CONFIDENCE_MIN=0.9
```

Notes:
- `--test` force l’URL de test; sinon l’URL de prod est utilisée.
- `N8N_VERIFY_SSL` peut être `false` (dev) ou un chemin de CA (prod).

## Webhook n8n: formats pris en charge
- Liste simple: `[{\"title\": \"...\", \"author\": \"...\"}]` → remappé vers `titre`/`auteur`.
- Dict normalisé: `{ \"titre\": \"...\", \"auteur\": \"...\", \"confiance\": \"...\", \"explication\": \"...\" }`.
- Liste avec `output`: `[{ \"output\": { ... } }]`.

En mode `--test`, la réponse brute est affichée et rien d’autre n’est exigé.

## Docker / Compose
1) Remplir `.env` (voir plus haut) et placer vos certs TLS dans `certs/`.
2) Lancer:
```
docker compose up --build
```

Tester le script dans le conteneur:
```
docker compose exec epub-agent \
  python src/epub_metadata.py --limit 10 --dry-run
```

## Arborescence
```
.
├── src/epub_metadata.py      # Script principal
├── src/test_n8n_webhook.py   # Test rapide du webhook
├── doc/                      # Guides & références
│  ├── usage.md               # Guide d’utilisation (inclut n8n et modes)
│  └── reference.md           # Référence fonctions & CLI
├── docker-compose.yml        # n8n + agent Python (+ Ollama en option)
├── Dockerfile                # Image du script
└── AGENTS.md                 # Notes pour agents/outils automatisés
```

## Liens utiles
- Guide: `doc/usage.md`
- Référence: `doc/reference.md`

