# Guide d'utilisation

## Pré-requis locaux

1. Python 3.11+
2. `pip install -r requirements.txt`

## Lancer le script en local

```bash
python src/epub_metadata.py --folder /chemin/vers/mes/epub --dry-run --limit 5
```

- `--dry-run` (par défaut) évite les renommages.
- `--limit` permet de couper après X fichiers.
- Les variables `EPUB_SOURCE_DIR`, `CONFIDENCE_MIN`, `N8N_WEBHOOK_*` se lisent depuis l'environnement.

## Configuration centralisée (.env)

Créez un fichier `.env` à la racine pour concentrer toutes les options :

```env
EPUB_ROOT=G:/livres bruts
EPUB_SOURCE_DIR=/data
EPUB_DEST=G:/Livres_sorted
LOG_DIR=/log
EPUB_LOG_FILE=n8n_response.json

N8N_WEBHOOK_TEST_URL=https://192.168.1.56:5678/webhook-test/epub-metadata
N8N_WEBHOOK_PROD_URL=https://192.168.1.56:5678/webhook/epub-metadata
N8N_MODE=test
N8N_VERIFY_SSL=true

CONFIDENCE_MIN=0.9
```

- `EPUB_ROOT` sert à monter les EPUB dans Docker et est transmis dans le payload (`root`).
- `EPUB_DEST` sera utilisé plus tard pour déplacer les livres renommés (elle figure déjà dans le payload).
- `N8N_MODE` règle l'URL utilisée (`test` ou `prod`).
- `LOG_DIR`/`EPUB_LOG_FILE` pointent vers `/log/n8n_response.json` ; chaque ressource est logguée au format JSON.

## Via docker-compose

`docker-compose.yml` lance :

- **n8n** (port 5678) : webhook sécurisé avec TLS.
- **ollama** (port 11434) : serveur local de modèles (peut être désactivé si vous utilisez une instance Windows).
- **epub-agent** : script Python lise `/data` et appelle n8n.

Le service `epub-agent` monte automatiquement le chemin `EPUB_ROOT` et les certificates :

```yaml
epub-agent:
  build: .
  restart: unless-stopped
  depends_on:
    n8n:
      condition: service_started
  environment:
    - EPUB_SOURCE_DIR=/data
  volumes:
    - ${EPUB_ROOT:-./ebooks}:/data:rw
    - ./certs:/certs:ro
```

### Lancer la stack

```bash
docker compose up --build
```

### Tester un lot limité d’EPUB

```bash
docker compose run --rm --no-deps epub-agent --limit 10 --dry-run
```

- La commande appuie uniquement sur `--limit` et `--dry-run` ; tout le reste (webhook, root, log, TLS) vient de `.env`.
- `--no-dry-run` bascule les renommages en production.

## Journaux et résultats

Chaque EPUB traité ajoute une ligne JSON dans `EPUB_LOG_FILE` (ni `null`, ni rien):

```json
{
  "filename": "MonLivre.epub",
  "path": "/data/MonLivre.epub",
  "titre": "...",
  "auteur": "...",
  "confiance": "0.81",
  "root": "G:/livres bruts",
  "metadata": {"title":"","creator":""...},
  "payload": {"filename":"MonLivre.epub","root":"G:/livres bruts",...}
}
```

Tu peux ensuite consommer ce log pour alimenter n8n ou ton analyse.
