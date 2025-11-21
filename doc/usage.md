# Guide d'utilisation

Ce guide couvre l'exÃ©cution locale et via Docker, ainsi que la configuration n8n
(certificats TLS, variables d'environnement, modes `--test` vs normal).

## Certificats TLS (n8n)

Le service n8n est exposÃ© en HTTPS et `docker-compose.yml` monte le dossier `certs/`
dans les conteneurs. Tu dois simplement y placer une paire `n8n.crt` (certificat)
et `n8n.key` (clÃ© privÃ©e).

### Option recommandÃ©e : `mkcert` (Windows / macOS / Linux)

`mkcert` gÃ©nÃ¨re facilement des certificats valides pour ton navigateur et tes outils locaux.

1. Installe `mkcert` : voir la doc officielle <https://github.com/FiloSottile/mkcert>.
2. Dans le dossier du projet :

   ```bash
   cd /chemin/vers/sortbook_v3/certs
   mkcert -install
   mkcert 192.168.1.56
   ```

3. Renomme les fichiers gÃ©nÃ©rÃ©s si besoin :

   - `192.168.1.56.pem` â†’ `n8n.crt`
   - `192.168.1.56-key.pem` â†’ `n8n.key`

4. Relance `docker compose up --build`.

### Option alternative : OpenSSL

Si tu ne peux pas utiliser `mkcert`, tu peux crÃ©er un certificat autosignÃ© avec OpenSSL
(attention, il faudra l'ajouter manuellement aux CA de confiance si tu veux Ã©viter les alertes).

- **Windows (PowerShell, OpenSSL installÃ©)** :

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

Ces variables dÃ©finissent comment le script Python interagit avec votre instance n8n. Elles sont lues depuis l'environnement (par exemple, via un fichier `.env` Ã  la racine du projet).

-   `N8N_WEBHOOK_PROD_URL` : URL du webhook n8n de production (utilisÃ© par dÃ©faut).
-   `N8N_WEBHOOK_TEST_URL` : URL du webhook n8n de test (utilisÃ© avec l'argument CLI `--test`).
-   `N8N_VERIFY_SSL` : ContrÃ´le la vÃ©rification SSL des requÃªtes HTTP vers n8n.
    -   `false`, `0`, `no`, `non` : DÃ©sactive la vÃ©rification SSL.
    -   `true`, `1`, `yes`, `oui` (par dÃ©faut si non dÃ©fini) : Active la vÃ©rification SSL.
    -   Tout autre chemin : SpÃ©cifie un chemin vers un fichier de certificat CA personnalisÃ© (par exemple, `/certs/n8n.crt`).
-   `N8N_TIMEOUT` : DÃ©lai maximum en secondes pour l'appel HTTP au webhook n8n (par dÃ©faut `120.0`).

**SÃ©lection de l'URL d'appel :**

-   **Sans argument `--test`** : Le script utilise la `N8N_WEBHOOK_PROD_URL` si elle est dÃ©finie. Sinon, il utilise l'URL par dÃ©faut `http://localhost:5678/webhook/epub-metadata`.
-   **Avec argument `--test`** : Le script utilise la `N8N_WEBHOOK_TEST_URL` si elle est dÃ©finie. Sinon, il utilise l'URL par dÃ©faut `http://localhost:5678/webhook/epub-metadata`.

## PrÃ©â€‘requis locaux

1.  Python 3.9+
2.  Les dÃ©pendances Python installÃ©es (`pip install -r requirements.txt`).

## Lancer le script en local

```bash
python src/epub_metadata.py --folder /chemin/vers/mes/epub --dry-run --limit 5
```

-   `--dry-run` : (par dÃ©faut si aucune option de renommage n'est active) Ã©vite les renommages effectifs des fichiers sur le disque.
-   `--limit N` : Permet de limiter le traitement aux `N` premiers fichiers EPUB trouvÃ©s.
-   `--folder PATH` : SpÃ©cifie le dossier Ã  traiter. Si non fourni, le script utilise la variable d'environnement `EPUB_SOURCE_DIR` ou demande Ã  l'utilisateur.
-   `--confidence-min FLOAT` : Surcharge le seuil de confiance minimal dÃ©fini par la variable d'environnement `CONFIDENCE_MIN`.
-   `--test` : Active le mode test (utilise `N8N_WEBHOOK_TEST_URL`, affiche la rÃ©ponse brute de n8n, pas de renommage).

Les variables d'environnement (`EPUB_SOURCE_DIR`, `CONFIDENCE_MIN`, `N8N_WEBHOOK_*`, etc.) sont lues depuis l'environnement systÃ¨me ou un fichier `.env`.

Pour passer en mode "production" et autoriser le renommage rÃ©el, lancez la commande **sans** l'argument `--dry-run` (et assurez-vous que `CONFIDENCE_MIN` est rÃ©glÃ© au seuil dÃ©sirÃ©).

## Configuration centralisÃ©e (.env)

Il est fortement recommandÃ© de crÃ©er un fichier `.env` Ã  la racine de votre projet pour centraliser toutes les options de configuration. Un fichier `/.env.example` est fourni comme modÃ¨le.

Voici les variables d'environnement principales :

-   **`EPUB_ROOT`** : Chemin local vers le dossier racine contenant vos EPUB. Ce chemin est montÃ© dans le conteneur Docker de l'agent sur `/data`. Il est Ã©galement transmis dans le `payload` envoyÃ© Ã  n8n sous la clÃ© `root`.
-   **`EPUB_SOURCE_DIR`** : Le chemin *Ã  l'intÃ©rieur du conteneur* oÃ¹ le script s'attend Ã  trouver les EPUB (doit correspondre au point de montage de `EPUB_ROOT`, gÃ©nÃ©ralement `/data`).
-   **`EPUB_DEST`** : Chemin local vers le dossier de destination pour les EPUB renommÃ©s. Si non spÃ©cifiÃ©, les fichiers sont renommÃ©s sur place. Cette valeur est Ã©galement incluse dans le `payload` n8n.
-   **`LOG_DIR`** : RÃ©pertoire oÃ¹ sera stockÃ© le fichier de log JSONL.
-   **`EPUB_LOG_FILE`** : Nom du fichier de log JSONL (par dÃ©faut `n8n_response.json`).
-   **`N8N_WEBHOOK_PROD_URL`**, **`N8N_WEBHOOK_TEST_URL`**, **`N8N_VERIFY_SSL`**, **`N8N_TIMEOUT`** : Voir la section prÃ©cÃ©dente pour les dÃ©tails de configuration de n8n.
-   **`CONFIDENCE_MIN`** : Seuil de confiance minimal (float entre 0.0 et 1.0) requis pour qu'un fichier soit renommÃ© automatiquement.
-   **`DEFAULT_MAX_TEXT_CHARS`** : Nombre maximal de caractÃ¨res de texte Ã  extraire de l'EPUB pour l'analyse par n8n (par dÃ©faut `4000`).
-   **`DEFAULT_SLUG_MAX_LENGTH`** : Longueur maximale pour les "slugs" gÃ©nÃ©rÃ©s pour les noms de fichiers (par dÃ©faut `150`).

Ces variables garantissent que le script et les services Docker fonctionnent avec la mÃªme configuration.

## Via docker-compose

Le fichier `docker-compose.yml` configure une stack complÃ¨te pour le projet :

-   **n8n** (port `5678`) : Le service d'orchestration des workflows, configurÃ© pour utiliser HTTPS (si les certificats sont prÃ©sents dans `./certs`).
-   **ollama** (port `11434`) : Un serveur local de modÃ¨les LLM (optionnel, activÃ© via un profil Docker Compose).
-   **epub-agent** : Le conteneur Python qui exÃ©cute le script principal. Il est construit Ã  partir de votre code local et configurÃ© pour interagir avec n8n.

### Configuration du service `epub-agent`

Le service `epub-agent` est prÃ©configurÃ© pour monter les volumes nÃ©cessaires :

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
    - .:/app:rw                      # Monte le dossier racine du projet pour l'exÃ©cution du script.
    - ./certs:/certs:ro              # AccÃ¨s aux certificats pour la validation SSL.
```

### Lancer la stack Docker Compose

Pour dÃ©marrer n8n et l'agent Python :

```bash
docker compose up --build -d
```

Pour inclure Ã©galement le service Ollama (pour un LLM local) :

```bash
docker compose --profile ollama up --build -d
```

> **Recommandation :** Pour des raisons de fiabilitÃ© et de gestion des ressources (GPU notamment), il est souvent prÃ©fÃ©rable d'installer et de gÃ©rer Ollama directement sur votre machine hÃ´te plutÃ´t que d'utiliser la version conteneurisÃ©e. Vous pouvez ensuite configurer n8n pour se connecter Ã  cette instance externe via `OLLAMA_HOST`.

### Tester le script dans le conteneur

Vous pouvez exÃ©cuter le script `epub_metadata.py` directement Ã  l'intÃ©rieur du conteneur `epub-agent` :

```bash
docker compose exec epub-agent \
  python src/epub_metadata.py --limit 10 --dry-run --folder /data
```

Notez que `--folder /data` indique au script de rechercher les EPUB dans le rÃ©pertoire `/data` *Ã  l'intÃ©rieur du conteneur*, qui est le point de montage de votre `EPUB_ROOT` local.

La commande ci-dessus utilise `--limit` et `--dry-run` pour un test sÃ»r. Toutes les autres configurations (URLs de webhook, chemins de log, seuils de confiance) sont automatiquement lues depuis les variables d'environnement configurÃ©es dans le `.env` de votre projet et passÃ©es au conteneur.

## Journaux et rÃ©sultats

Chaque EPUB traitÃ© gÃ©nÃ¨re une ligne au format JSONL dans le fichier de log spÃ©cifiÃ© par `EPUB_LOG_FILE` (`n8n_response.json` par dÃ©faut). Ce log contient toutes les informations pertinentes pour le suivi et l'analyse post-traitement :

```json
{
  "filename": "MonLivre.epub",
  "path": "/chemin/complet/vers/MonLivre.epub",
  "titre": "Titre du livre",
  "auteur": "Nom de l'auteur",
  "confiance": "0.81",
  "explication": "Correspondance trouvÃ©e via...",
  "destination": "/chemin/de/destination/specifie",
  "metadata": {
    "title": "Titre OPF",
    "creator": "CrÃ©ateur OPF",
    "publisher": "Ã‰diteur OPF",
    "language": "fr",
    "identifier": "identifiant-unique",
    "description": "Description de l'EPUB"
  },
  "payload": {
    "filename": "MonLivre.epub",
    "root": "/chemin/racine/des/epubs",
    "destination": "/chemin/de/destination/specifie",
    "text": "Extrait de texte envoyÃ© Ã  n8n...",
    "metadata": { /* ... mÃªmes mÃ©tadonnÃ©es que ci-dessus ... */ }
  }
}
```

Ce fichier de log peut Ãªtre ensuite utilisÃ© pour alimenter d'autres systÃ¨mes, faire des analyses statistiques ou simplement pour vÃ©rifier le dÃ©roulement des opÃ©rations.

## Mode test vs normal

Le script peut Ãªtre exÃ©cutÃ© en deux modes principaux en ce qui concerne l'interaction avec n8n :

-   **Mode `--test`** :
    -   Le script utilise l'URL de test (`N8N_WEBHOOK_TEST_URL`).
    -   Il n'attend pas de format JSON particulier de la part de n8n et affiche la rÃ©ponse brute du webhook directement dans la console.
    -   Aucun renommage de fichier n'est effectuÃ©, quelle que soit la rÃ©ponse.
    Ce mode est idÃ©al pour le dÃ©bogage de vos workflows n8n.

-   **Mode normal (sans `--test`)** :
    -   Le script utilise l'URL de production (`N8N_WEBHOOK_PROD_URL`).
    -   Il attend une rÃ©ponse JSON structurÃ©e de n8n pour pouvoir en extraire les informations de renommage (`titre`, `auteur`, `confiance`, `explication`).
    -   La logique mÃ©tier de renommage (basÃ©e sur la confiance et le titre) est appliquÃ©e.

**Formats de rÃ©ponse n8n acceptÃ©s en mode normal :**

Le script est flexible et peut interprÃ©ter plusieurs structures de rÃ©ponse JSON pour en extraire un `EpubResult` (titre, auteur, confiance, explication) :

-   **Format direct (recommandÃ©) :** Un objet JSON contenant directement les clÃ©s `titre`, `auteur`, `confiance`, `explication`.
-   **ClÃ©s alternatives `title`/`author` :** Si votre workflow renvoie `title` et `author` (en anglais) au lieu de `titre` et `auteur` (en franÃ§ais), elles seront automatiquement converties.
-   **Format encapsulÃ© (`output`) :** Un objet JSON contenant un sous-objet `output` qui contient lui-mÃªme les informations de renommage.
-   **Format liste :** Le script peut Ã©galement traiter une liste d'objets, en ne considÃ©rant que le premier Ã©lÃ©ment. Ces objets peuvent Ãªtre au format direct ou encapsulÃ©.

Pour des exemples dÃ©taillÃ©s de ces formats, veuillez consulter la section "Webhook n8n : Formats de rÃ©ponse pris en charge" dans le `README.md` ou `AGENTS.md`.

