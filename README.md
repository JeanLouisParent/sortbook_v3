# sortbook_v3

Automatise l'identification et le renommage de fichiers EPUB en s'appuyant sur un workflow n8n.

## Fonctionnalités
- Extraction rapide d'un texte pertinent depuis chaque EPUB.
- Appel HTTP à un webhook n8n qui renvoie titre, auteur, confiance et explication.
- Renommage conditionnel selon le niveau de confiance et la présence d'un titre valide.
- Mode simulation (`dry-run`) pour vérifier les actions avant exécution.

## Structure

```
.
├── docker-compose.yml      # n8n + agent Python + Ollama
├── Dockerfile              # Image du script Python
├── requirements.txt
├── src/epub_metadata.py    # Script principal
└── doc/                    # Documentation (agents, guide d'usage)
```

## Installation rapide

```bash
pip install -r requirements.txt
python src/epub_metadata.py --folder /chemin/vers/ebooks --dry-run
```

Le script peut lire les variables `N8N_WEBHOOK_URL`, `EPUB_SOURCE_DIR`, `DRY_RUN` et `CONFIDENCE_MIN`
depuis l'environnement. Passez `--no-dry-run` ou `DRY_RUN=false` pour renommer réellement.

### Test rapide du webhook

```bash
python src/test_n8n_webhook.py
```

Variables utiles :
- `N8N_WEBHOOK_URL` : change l'URL ciblée.
- `N8N_TEST_TEXT` : texte envoyé (défaut : `test`).
## Docker / Compose

Cr�ez ou mettez � jour `.env` � la racine :

```env
EPUB_ROOT=G:/livres bruts
EPUB_SOURCE_DIR=/data
EPUB_DEST=G:/Livres_sorted
LOG_DIR=/app/log
EPUB_LOG_FILE=n8n_response.json

N8N_WEBHOOK_TEST_URL=https://192.168.1.56:5678/webhook-test/epub-metadata
N8N_WEBHOOK_PROD_URL=https://192.168.1.56:5678/webhook/epub-metadata
N8N_MODE=prod
N8N_VERIFY_SSL=/certs/n8n.crt

CONFIDENCE_MIN=0.9
```

`docker-compose.yml` utilise `${EPUB_ROOT}` pour monter ton dossier (`${EPUB_ROOT:-./ebooks}:/data:rw`), monte le repo dans `/app` et partage `certs/` pour TLS.
Ensuite lance la stack :

```bash
docker compose up --build
```

Les services expos�s :
- `n8n` (port 5678) pour le webhook, avec TLS via les certs.
- `ollama` (port 11434) qui h�berge les mod�les.
- `epub-agent` qui lit `/data` (ton dossier issu de `EPUB_ROOT`) et ex�cute le script.

Pour tester rapidement le traitement en mode `dry-run` avec limitation :

```bash
docker compose run --rm --no-deps epub-agent --limit 10 --dry-run
```

## Documentation
- `doc/usage.md` : commandes CLI, Docker et docker-compose détaillées.

Depuis Docker (service `epub-agent`), pour tester la route de **test** du webhook (`webhook-test/epub-metadata`) avec le certificat local et HTTPS :

```bash
docker compose run --rm --entrypoint python -v ${PWD}/certs:/certs:ro -e N8N_WEBHOOK_URL=https://192.168.1.56:5678/webhook-test/epub-metadata -e REQUESTS_CA_BUNDLE=/certs/n8n.crt epub-agent src/test_n8n_webhook.py
```

Et pour la route **normale** (`webhook/epub-metadata`) :

```bash
docker compose run --rm --entrypoint python -v ${PWD}/certs:/certs:ro -e N8N_WEBHOOK_URL=https://192.168.1.56:5678/webhook/epub-metadata -e REQUESTS_CA_BUNDLE=/certs/n8n.crt epub-agent src/test_n8n_webhook.py
```

