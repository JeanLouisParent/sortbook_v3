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

Ces variables définissent comment le script Python interagit avec votre instance n8n. Elles sont lues depuis l'environnement (par exemple, via un fichier `.env` à la racine du projet).

-   `N8N_WEBHOOK_PROD_URL` : URL du webhook n8n de production (utilisé par défaut).
-   `N8N_WEBHOOK_TEST_URL` : URL du webhook n8n de test (utilisé avec l'argument CLI `--test`).
-   `N8N_VERIFY_SSL` : Contrôle la vérification SSL des requêtes HTTP vers n8n.
    -   `false`, `0`, `no`, `non` : Désactive la vérification SSL.
    -   `true`, `1`, `yes`, `oui` (par défaut si non défini) : Active la vérification SSL.
    -   Tout autre chemin : Spécifie un chemin vers un fichier de certificat CA personnalisé (par exemple, `/certs/n8n.crt`).
-   `N8N_TIMEOUT` : Délai maximum en secondes pour l'appel HTTP au webhook n8n (par défaut `120.0`).

**Sélection de l'URL d'appel :**

-   **Sans argument `--test`** : Le script utilise la `N8N_WEBHOOK_PROD_URL` si elle est définie. Sinon, il utilise l'URL par défaut `http://localhost:5678/webhook/epub-metadata`.
-   **Avec argument `--test`** : Le script utilise la `N8N_WEBHOOK_TEST_URL` si elle est définie. Sinon, il utilise l'URL par défaut `http://localhost:5678/webhook/epub-metadata`.

## Pré‑requis locaux

1.  Python 3.9+
2.  Les dépendances Python installées (`pip install -r requirements.txt`).

## Lancer le script en local

```bash
python src/epub_metadata.py --folder /chemin/vers/mes/epub --dry-run --limit 5
```

-   `--dry-run` : (par défaut si aucune option de renommage n'est active) évite les renommages effectifs des fichiers sur le disque.
-   `--limit N` : Permet de limiter le traitement aux `N` premiers fichiers EPUB trouvés.
-   `--folder PATH` : Spécifie le dossier à traiter. Si non fourni, le script utilise la variable d'environnement `EPUB_SOURCE_DIR` ou demande à l'utilisateur.
-   `--confidence-min FLOAT` : Surcharge le seuil de confiance minimal défini par la variable d'environnement `CONFIDENCE_MIN`.
-   `--test` : Active le mode test (utilise `N8N_WEBHOOK_TEST_URL`, affiche la réponse brute de n8n, pas de renommage).

Les variables d'environnement (`EPUB_SOURCE_DIR`, `CONFIDENCE_MIN`, `N8N_WEBHOOK_*`, etc.) sont lues depuis l'environnement système ou un fichier `.env`.

Pour passer en mode "production" et autoriser le renommage réel, lancez la commande **sans** l'argument `--dry-run` (et assurez-vous que `CONFIDENCE_MIN` est réglé au seuil désiré).

## Configuration centralisée (.env)

Il est fortement recommandé de créer un fichier `.env` à la racine de votre projet pour centraliser toutes les options de configuration. Un fichier `/.env.example` est fourni comme modèle.

Voici les variables d'environnement principales :

-   **`EPUB_ROOT`** : Chemin local vers le dossier racine contenant vos EPUB. Ce chemin est monté dans le conteneur Docker de l'agent sur `/data`. Il est également transmis dans le `payload` envoyé à n8n sous la clé `root`.
-   **`EPUB_SOURCE_DIR`** : Le chemin *à l'intérieur du conteneur* où le script s'attend à trouver les EPUB (doit correspondre au point de montage de `EPUB_ROOT`, généralement `/data`).
-   **`EPUB_DEST`** : Chemin local vers le dossier de destination pour les EPUB renommés. Si non spécifié, les fichiers sont renommés sur place. Cette valeur est également incluse dans le `payload` n8n.
-   **`LOG_DIR`** : Répertoire où sera stocké le fichier de log JSONL.
-   **`EPUB_LOG_FILE`** : Nom du fichier de log JSONL (par défaut `n8n_response.json`).
-   **`N8N_WEBHOOK_PROD_URL`**, **`N8N_WEBHOOK_TEST_URL`**, **`N8N_VERIFY_SSL`**, **`N8N_TIMEOUT`** : Voir la section précédente pour les détails de configuration de n8n.
-   **`CONFIDENCE_MIN`** : Seuil de confiance minimal (float entre 0.0 et 1.0) requis pour qu'un fichier soit renommé automatiquement.
-   **`DEFAULT_MAX_TEXT_CHARS`** : Nombre maximal de caractères de texte à extraire de l'EPUB pour l'analyse par n8n (par défaut `4000`).
-   **`DEFAULT_SLUG_MAX_LENGTH`** : Longueur maximale pour les "slugs" générés pour les noms de fichiers (par défaut `150`).

Ces variables garantissent que le script et les services Docker fonctionnent avec la même configuration.

## Via docker-compose

Le fichier `docker-compose.yml` configure une stack complète pour le projet :

-   **n8n** (port `5678`) : Le service d'orchestration des workflows, configuré pour utiliser HTTPS (si les certificats sont présents dans `./certs`).
-   **ollama** (port `11434`) : Un serveur local de modèles LLM (optionnel, activé via un profil Docker Compose).
-   **epub-agent** : Le conteneur Python qui exécute le script principal. Il est construit à partir de votre code local et configuré pour interagir avec n8n.

### Configuration du service `epub-agent`

Le service `epub-agent` est préconfiguré pour monter les volumes nécessaires :

```yaml
epub-agent:
  build: .
  restart: unless-stopped
  depends_on:
    n8n:
      condition: service_started
  environment:
    - EPUB_SOURCE_DIR=/data # Le script recherche les EPUB ici, dans le conteneur.
  volumes:
    - ${EPUB_ROOT:-./ebooks}:/data:rw # Monte votre dossier local d'EPUB dans /data du conteneur.
    - .:/app:rw                      # Monte le dossier racine du projet pour l'exécution du script.
    - ./certs:/certs:ro              # Accès aux certificats pour la validation SSL.
```

### Lancer la stack Docker Compose

Pour démarrer n8n et l'agent Python :

```bash
docker compose up --build -d
```

Pour inclure également le service Ollama (pour un LLM local) :

```bash
docker compose --profile ollama up --build -d
```

> **Recommandation :** Pour des raisons de fiabilité et de gestion des ressources (GPU notamment), il est souvent préférable d'installer et de gérer Ollama directement sur votre machine hôte plutôt que d'utiliser la version conteneurisée. Vous pouvez ensuite configurer n8n pour se connecter à cette instance externe via `OLLAMA_HOST`.

### Tester le script dans le conteneur

Vous pouvez exécuter le script `epub_metadata.py` directement à l'intérieur du conteneur `epub-agent` :

```bash
docker compose exec epub-agent \
  python src/epub_metadata.py --limit 10 --dry-run --folder /data
```

Notez que `--folder /data` indique au script de rechercher les EPUB dans le répertoire `/data` *à l'intérieur du conteneur*, qui est le point de montage de votre `EPUB_ROOT` local.

La commande ci-dessus utilise `--limit` et `--dry-run` pour un test sûr. Toutes les autres configurations (URLs de webhook, chemins de log, seuils de confiance) sont automatiquement lues depuis les variables d'environnement configurées dans le `.env` de votre projet et passées au conteneur.

## Journaux et résultats

Chaque EPUB traité génère une ligne au format JSONL dans le fichier de log spécifié par `EPUB_LOG_FILE` (`n8n_response.json` par défaut). Ce log contient toutes les informations pertinentes pour le suivi et l'analyse post-traitement :

```json
{
  "filename": "MonLivre.epub",
  "path": "/chemin/complet/vers/MonLivre.epub",
  "titre": "Titre du livre",
  "auteur": "Nom de l'auteur",
  "confiance": "0.81",
  "explication": "Correspondance trouvée via...",
  "destination": "/chemin/de/destination/specifie",
  "metadata": {
    "title": "Titre OPF",
    "creator": "Créateur OPF",
    "publisher": "Éditeur OPF",
    "language": "fr",
    "identifier": "identifiant-unique",
    "description": "Description de l'EPUB"
  },
  "payload": {
    "filename": "MonLivre.epub",
    "root": "/chemin/racine/des/epubs",
    "destination": "/chemin/de/destination/specifie",
    "text": "Extrait de texte envoyé à n8n...",
    "metadata": { /* ... mêmes métadonnées que ci-dessus ... */ }
  }
}
```

Ce fichier de log peut être ensuite utilisé pour alimenter d'autres systèmes, faire des analyses statistiques ou simplement pour vérifier le déroulement des opérations.

## Mode test vs normal

Le script peut être exécuté en deux modes principaux en ce qui concerne l'interaction avec n8n :

-   **Mode `--test`** :
    -   Le script utilise l'URL de test (`N8N_WEBHOOK_TEST_URL`).
    -   Il n'attend pas de format JSON particulier de la part de n8n et affiche la réponse brute du webhook directement dans la console.
    -   Aucun renommage de fichier n'est effectué, quelle que soit la réponse.
    Ce mode est idéal pour le débogage de vos workflows n8n.

-   **Mode normal (sans `--test`)** :
    -   Le script utilise l'URL de production (`N8N_WEBHOOK_PROD_URL`).
    -   Il attend une réponse JSON structurée de n8n pour pouvoir en extraire les informations de renommage (`titre`, `auteur`, `confiance`, `explication`).
    -   La logique métier de renommage (basée sur la confiance et le titre) est appliquée.

**Formats de réponse n8n acceptés en mode normal :**

Le script est flexible et peut interpréter plusieurs structures de réponse JSON pour en extraire un `EpubResult` (titre, auteur, confiance, explication) :

-   **Format direct (recommandé) :** Un objet JSON contenant directement les clés `titre`, `auteur`, `confiance`, `explication`.
-   **Clés alternatives `title`/`author` :** Si votre workflow renvoie `title` et `author` (en anglais) au lieu de `titre` et `auteur` (en français), elles seront automatiquement converties.
-   **Format encapsulé (`output`) :** Un objet JSON contenant un sous-objet `output` qui contient lui-même les informations de renommage.
-   **Format liste :** Le script peut également traiter une liste d'objets, en ne considérant que le premier élément. Ces objets peuvent être au format direct ou encapsulé.

Pour des exemples détaillés de ces formats, veuillez consulter la section "Webhook n8n : Formats de réponse pris en charge" dans le `README.md` ou `AGENTS.md`.
