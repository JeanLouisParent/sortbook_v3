# Guide d'utilisation

## PrÃ©-requis locaux

1. Python 3.11+
2. `pip install -r requirements.txt` (seul le paquet `requests` est nÃ©cessaire)

## Lancer le script en local

```bash
python src/epub_metadata.py --folder /chemin/vers/mes/epub --dry-run
```

- Passer `--no-dry-run` pour renommer rÃ©ellement.
- Pour modifier le seuil de confiance : `--confidence-min Ã©levÃ©e`.
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

- `n8n` : workflow IA (exposÃ© sur `localhost:5678`), image officielle (tag 1.119.2) avec donnÃ©es versionnÃ©es via `n8n_data/`.
- `ollama` : serveur local Ollama (`localhost:11434`) qui tÃ©lÃ©charge automatiquement `mistral:7b`.
- `epub-agent` : exÃ©cute pÃ©riodiquement le script (dry-run activÃ© par dÃ©faut). Adaptez le volume `./ebooks:/data`.

Commande :

```bash
docker compose up --build
```

Surveillez ensuite les logs des services (`n8n`, `ollama`, `epub-agent`) pour vÃ©rifier le bon dÃ©roulement du flux. Lorsque vous mettez Ã  jour n8n pour appeler Ollama, utilisez l'URL interne `http://ollama:11434`. Le service Ollama tÃ©lÃ©charge `mistral:7b` au premier dÃ©marrage.
"

## Accès HTTPS à n8n en local (Windows -> Mac)

Pour exposer n8n en HTTPS depuis un serveur Windows vers un Mac, sans versionner les certificats dans Git :

1. Assurez-vous que le dossier `certs/` est présent à la racine du projet (il est ignoré par Git via `.gitignore`).
2. Sur le serveur Windows (ex. IP `192.168.1.56`), installez OpenSSL (Win64 OpenSSL Light) puis générez un certificat auto-signé :

```powershell
cd G:\Work\sortbook_v3
mkdir certs -Force

"C:\Program Files\OpenSSL-Win64\bin\openssl.exe" req -x509 -nodes -days 365 ^
  -newkey rsa:2048 ^
  -keyout certs/n8n.key ^
  -out certs/n8n.crt ^
  -subj "/CN=192.168.1.56"
```

3. Configurez le service `n8n` dans `docker-compose.yml` pour utiliser TLS directement :

```yaml
services:
  n8n:
    image: n8nio/n8n:1.119.2
    restart: always
    ports:
      - "5678:5678"
    environment:
      - GENERIC_TIMEZONE=Europe/Paris
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=passn8n
      - N8N_HOST=192.168.1.56
      - N8N_PROTOCOL=https
      - N8N_SSL_KEY=/certs/n8n.key
      - N8N_SSL_CERT=/certs/n8n.crt
      - N8N_SECURE_COOKIE=true
      - WEBHOOK_URL=https://192.168.1.56:5678/
    volumes:
      - ./n8n_data:/home/node/.n8n
      - ./certs:/certs:ro
```

4. Redémarrez les services :

```bash
docker compose down
docker compose up -d
```

5. Sur le Mac, importez `certs/n8n.crt` dans le Trousseau d'accès et marquez-le comme "toujours approuvé" pour SSL, puis accédez à n8n via :

```text
https://192.168.1.56:5678/
```

## Tester rapidement le webhook n8n depuis Docker

Pour tester la route de **test** de votre workflow (ex. `webhook-test/epub-metadata`) avec le script `src/test_n8n_webhook.py` depuis le conteneur `epub-agent` :

```bash
docker compose run --rm --entrypoint python -v ${PWD}/certs:/certs:ro -e N8N_WEBHOOK_URL=https://192.168.1.56:5678/webhook-test/epub-metadata -e REQUESTS_CA_BUNDLE=/certs/n8n.crt epub-agent src/test_n8n_webhook.py
```

Pour tester la route **normale** (production) du webhook (`webhook/epub-metadata`) :

```bash
docker compose run --rm --entrypoint python -v ${PWD}/certs:/certs:ro -e N8N_WEBHOOK_URL=https://192.168.1.56:5678/webhook/epub-metadata -e REQUESTS_CA_BUNDLE=/certs/n8n.crt epub-agent src/test_n8n_webhook.py
```
