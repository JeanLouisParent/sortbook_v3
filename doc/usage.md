# Guide d'utilisation

Ce guide couvre l'exécution locale et via Docker, ainsi que la configuration n8n
(certificats TLS, variables d'environnement, modes `--test` vs normal).

## Certificats TLS (n8n)

Le service n8n est exposé en HTTPS et `docker-compose.yml` monte le dossier `certs/`
dans les conteneurs. Tu dois simplement y placer une paire `n8n.crt` (certificat)
et `n8n.key` (clé privée).

### Option recommandée : `mkcert` (Windows / macOS / Linux)

`mkcert` génère facilement des certificats valides pour ton navigateur et tes outils locaux.

1. Installe `mkcert` : voir la doc officielle <https://github.com/FiloSottile/mkcert>.
2. Dans le dossier du projet :

   ```bash
   cd /chemin/vers/sortbook_v3/certs
   mkcert -install
   mkcert 192.168.1.56
   ```

3. Renomme les fichiers générés si besoin :

   - `192.168.1.56.pem` → `n8n.crt`
   - `192.168.1.56-key.pem` → `n8n.key`

4. Relance `docker compose up --build`.

### Option alternative : OpenSSL

Si tu ne peux pas utiliser `mkcert`, tu peux créer un certificat autosigné avec OpenSSL
(attention, il faudra l'ajouter manuellement aux CA de confiance si tu veux éviter les alertes).

- **Windows (PowerShell, OpenSSL installé)** :

  ```powershell
  cd G:\Work\sortbook_v3\certs
  openssl genrsa -out n8n.key 2048
  openssl req -new -x509 -key n8n.key -out n8n.crt -days 365 `
    -subj "/C=FR/ST=IDF/L=Paris/O=sortbook/OU=dev/CN=192.168.1.56"
  ```

- **Linux / macOS** :

  ```bash
  cd /chemin/vers/sortbook_v3/certs
  openssl genrsa -out n8n.key 2048
  openssl req -new -x509 -key n8n.key -out n8n.crt -days 365 \
    -subj "/C=FR/ST=IDF/L=Paris/O=sortbook/OU=dev/CN=192.168.1.56"
  ```

Ensuite :
- le conteneur n8n utilise `n8n.key` / `n8n.crt` pour TLS ;
- le script Python peut valider le certificat en pointant `REQUESTS_CA_BUNDLE`
  ou `N8N_VERIFY_SSL` vers `/certs/n8n.crt` (comme dans l'exemple du `README.md`).

## n8n : variables d'environnement et modes

Variables à définir (idéalement dans `.env`) :

- `N8N_WEBHOOK_PROD_URL` : URL du webhook n8n de production.
- `N8N_WEBHOOK_TEST_URL` : URL du webhook n8n de test.
- `N8N_VERIFY_SSL` : `false` pour désactiver TLS, ou chemin vers une CA/bundle (ex: `/certs/n8n.crt`).
- `N8N_TIMEOUT` : délai max (secondes) pour l'appel HTTP (défaut 120).

Sélection de l'URL d'appel :

- sans `--test` → `N8N_WEBHOOK_PROD_URL` si défini, sinon `http://localhost:5678/webhook/epub-metadata` ;
- avec `--test` → `N8N_WEBHOOK_TEST_URL` si défini, sinon `http://localhost:5678/webhook/epub-metadata`.

## Pré‑requis locaux

1. Python 3.11+
2. `pip install -r requirements.txt`

## Lancer le script en local

```bash
python src/epub_metadata.py --folder /chemin/vers/mes/epub --dry-run --limit 5
```

- `--dry-run` (par défaut) évite les renommages.
- `--limit` permet de couper après X fichiers.
- Les variables `EPUB_SOURCE_DIR`, `CONFIDENCE_MIN`, `N8N_WEBHOOK_*` se lisent depuis l'environnement.

Pour passer en mode "production", lance simplement la commande **sans** `--dry-run`
(et, si tu utilises la variable d'environnement, avec `DRY_RUN=false`).

## Configuration centralisée (.env)

Créez un fichier `.env` à la racine pour concentrer toutes les options (voir exemple dans le README).

- `EPUB_ROOT` sert à monter les EPUB dans Docker et est transmis dans le payload (`root`).
- `EPUB_DEST` pourra être utilisé plus tard pour déplacer les livres renommés (elle figure déjà dans le payload).
- `LOG_DIR`/`EPUB_LOG_FILE` définissent où le log JSON est écrit dans le conteneur.

## Via docker-compose

`docker-compose.yml` lance :

- **n8n** (port 5678) : webhook sécurisé avec TLS.
- **ollama** (port 11434) : serveur local de modèles (désactivé par défaut, profil `ollama`).
- **epub-agent** : conteneur Python qui lit `/data` et appelle n8n (scripts lancés à la main).

Le service `epub-agent` monte automatiquement le chemin `EPUB_ROOT` et les certificats :

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
    - .:/app:rw
    - ./certs:/certs:ro
```

### Lancer la stack

```bash
docker compose up --build
```

Par défaut, seuls n8n et `epub-agent` sont démarrés.  
Pour démarrer aussi le conteneur Ollama :

```bash
docker compose --profile ollama up --build
```

> Recommandation : pour des raisons de fiabilité et de gestion des credentials (n8n, API, etc.),
> il est conseillé d'installer Ollama "nativement" sur votre OS (Windows/macOS/Linux)
> et de le connecter à n8n via `OLLAMA_HOST`, plutôt que d'utiliser systématiquement le conteneur Docker.

### Tester un lot limité d'EPUB

```bash
docker compose exec epub-agent \
  python src/epub_metadata.py --limit 10 --dry-run
```

- La commande appuie uniquement sur `--limit` et `--dry-run` ; tout le reste (webhook, root, log, TLS) vient de `.env`.

## Journaux et résultats

Chaque EPUB traité ajoute une ligne JSON dans `EPUB_LOG_FILE` :

```json
{
  "filename": "MonLivre.epub",
  "path": "/data/MonLivre.epub",
  "titre": "...",
  "auteur": "...",
  "confiance": "0.81",
  "root": "G:/livres bruts",
  "metadata": {"title": "", "creator": ""},
  "payload": {"filename": "MonLivre.epub", "root": "G:/livres bruts"}
}
```

Tu peux ensuite consommer ce log pour alimenter n8n ou ton analyse.

## Mode test vs normal

- `--test` : le script n'attend pas de JSON particulier, affiche la réponse brute du webhook dans la console et n'applique pas de renommage.
- Sans `--test` : la réponse doit être au format attendu (JSON structuré) pour alimenter la logique métier (extraction titre/auteur, seuil de confiance, renommage éventuel).

Formats acceptés hors `--test` :

- Liste simple: `[{\"title\": \"...\", \"author\": \"...\"}]` → remappé vers `titre`/`auteur`.
- Dict normalisé: `{ \"titre\": \"...\", \"auteur\": \"...\", \"confiance\": \"...\", \"explication\": \"...\" }`.
- Liste avec `output`: `[{ \"output\": { ... } }]`.
