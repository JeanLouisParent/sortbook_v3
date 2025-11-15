# Guide d'utilisation

## Pré-requis locaux

1. Python 3.11+
2. `pip install -r requirements.txt` (seul le paquet `requests` est nécessaire)

## Lancer le script en local

```bash
python src/epub_metadata.py --folder /chemin/vers/mes/epub --dry-run
```

- Passer `--no-dry-run` pour renommer réellement.
- Pour modifier le seuil de confiance : `--confidence-min élevée`.
- Le webhook se configure via `export N8N_WEBHOOK_URL="http://localhost:5678/webhook/epub-metadata"`.

## Variables d'environnement utiles

```bash
export EPUB_SOURCE_DIR=/chemin/vers/mes/ebooks
export DRY_RUN=false
export CONFIDENCE_MIN=moyenne
export N8N_WEBHOOK_URL=https://n8n.exemple.com/webhook/epub-metadata
```

Lancer ensuite le script sans options : il lira ces variables et ne posera pas de question.

## Utilisation avec Docker

1. Placez vos EPUB dans un dossier local (ex. `./ebooks`).
2. Construisez l'image :

```bash
docker build -t sortbook-epub .
```

3. Lancez en montant le dossier :

```bash
docker run --rm \
  -e N8N_WEBHOOK_URL=http://host.docker.internal:5678/webhook/epub-metadata \
  -e DRY_RUN=false \
  -v $(pwd)/ebooks:/data \
  sortbook-epub
```

## Via docker-compose

Le fichier `docker-compose.yml` fournit trois services :

- `n8n` : workflow IA (exposé sur `localhost:5678`), image officielle (tag 1.119.2) avec données versionnées via `n8n_data/`.
- `ollama` : serveur local Ollama (`localhost:11434`) qui télécharge automatiquement `mistral:7b`.
- `epub-agent` : exécute périodiquement le script (dry-run activé par défaut). Adaptez le volume `./ebooks:/data`.

Commande :

```bash
docker compose up --build
```

Surveillez ensuite les logs des services (`n8n`, `ollama`, `epub-agent`) pour vérifier le bon déroulement du flux. Lorsque vous mettez à jour n8n pour appeler Ollama, utilisez l'URL interne `http://ollama:11434`. Le service Ollama télécharge `mistral:7b` au premier démarrage.
