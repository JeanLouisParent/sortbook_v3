# AGENTS: Architecture, Flux et Guidelines

## Vue d’ensemble

- Composants:
  - n8n: workflow orchestrant l’analyse sémantique (exposé via webhook HTTPS).
  - Agent Python (ce repo): lit les EPUB, extrait texte + métadonnées, appelle n8n, journalise et renomme selon la confiance.
  - Docker Compose: facilite l’orchestration (n8n, agent, Ollama en option).

## Flux de bout en bout

1) **Extraction :** L'agent Python parcourt les fichiers `.epub` dans le dossier source. Pour chaque EPUB, il extrait :
    *   Du texte brut (environ 4000 caractères par défaut, configurable via `DEFAULT_MAX_TEXT_CHARS`), en priorisant les sections comme la couverture ou la page de titre (via `PREFERRED_KEYWORDS`) pour une meilleure pertinence.
    *   Les métadonnées standard de l'EPUB (titre, auteur, éditeur, langue, identifiant, description) à partir du fichier OPF.
2) **Communication n8n :** L'agent envoie à n8n un `payload` JSON structuré contenant les informations extraites :
    ```json
    {
        "filename": "nom_du_fichier.epub",
        "root": "/chemin/racine/des/epubs",
        "destination": "/chemin/de/destination/par/defaut",
        "text": "Extrait de texte de l'EPUB...",
        "metadata": {
            "title": "Titre OPF",
            "creator": "Auteur OPF",
            "publisher": "Éditeur OPF",
            "language": "fr",
            "identifier": "urn:isbn:1234567890",
            "description": "Description OPF"
        }
    }
    ```
3) **Réponse n8n et Normalisation :** n8n effectue son analyse (généralement via un LLM) et renvoie une réponse. L'agent Python (via la fonction `_normalize_n8n_response`) est flexible et peut interpréter plusieurs formats de réponse pour en extraire un `EpubResult` (titre, auteur, confiance, explication). Les formats gérés incluent :
    *   **Format direct (recommandé) :** `{"titre": "...", "auteur": "...", "confiance": "0.95", "explication": "..."}`
    *   **Format encapsulé :** `{"output": {"titre": "...", "auteur": "...", ...}}`
    *   **Format liste :** `[{"titre": "...", "auteur": "...", ...}]` ou `[{"output": {"titre": "...", ...}}]`
    *   Les clés `title` et `author` sont automatiquement remappées vers `titre` et `auteur` si elles sont présentes.
    En mode `test`, la réponse brute de n8n est affichée et aucune normalisation n'est tentée.
4) **Log et Renommage Conditionnel :**
    *   L'agent journalise systématiquement une ligne JSONL par fichier traité dans `EPUB_LOG_FILE`, incluant toutes les données du `payload`, la réponse normalisée de n8n et le chemin de destination.
    *   Le renommage est proposé/effectué uniquement si :
        *   Le `titre` renvoyé par n8n n'est pas "inconnu" (insensible à la casse).
        *   La `confiance` renvoyée par n8n (convertie en float) est supérieure ou égale à `CONFIDENCE_MIN` (défini par une variable d'environnement ou l'argument CLI `--confidence-min`).
    *   Le nouveau nom de fichier est généré via `slugify` (max 150 caractères par défaut, configurable via `DEFAULT_SLUG_MAX_LENGTH`), et gère les conflits de noms en ajoutant un suffixe numérique (ex: `(1)`).

## Répartition des fichiers

-   `src/epub_metadata.py` (script principal)
    -   **Dataclasses clés :**
        -   `Config` : Gère le chargement de la configuration depuis les variables d'environnement et les arguments CLI. Contient `webhook_url`, `verify_ssl`, `timeout`, `log_path`, `epub_root_label`, `dest_path`, `confidence_min`.
        -   `EpubResult` : Représente la réponse normalisée de n8n, avec `titre`, `auteur`, `confiance`, `explication`. Inclut la logique `get_confidence_value` et `should_rename` pour le renommage conditionnel.
        -   `EpubMetadata` : Contient les métadonnées extraites directement du fichier OPF de l'EPUB (`title`, `creator`, `publisher`, `language`, `identifier`, `description`).
    -   **Fonctions clés :**
        -   `extract_text_from_epub(epub_path, max_chars)` : Extrait le texte nettoyé de l'EPUB en priorisant les sections pertinentes (`PREFERRED_KEYWORDS`). Limite l'extraction à `max_chars` (par défaut `DEFAULT_MAX_TEXT_CHARS = 4000`).
        -   `extract_metadata_from_epub(epub_path)` : Lit les métadonnées Dublin Core du fichier OPF de l'EPUB et les renvoie sous forme d'objet `EpubMetadata`.
        -   `call_n8n(payload, config, test_mode)` : Envoie le `payload` JSON à l'URL de webhook n8n configurée. Gère les différents formats de réponse de n8n via `_normalize_n8n_response` pour les convertir en un format `EpubResult` cohérent.
        -   `slugify(text, max_length)` : Crée un nom de fichier sûr et nettoyé à partir d'une chaîne de caractères, tronqué à `max_length` (par défaut `DEFAULT_SLUG_MAX_LENGTH = 150`).
        -   `log_result(...)` : Ajoute un enregistrement JSONL au fichier de log spécifié par `config.log_path`.
        -   `rename_epub(...)` : Renomme l'EPUB sur le disque en fonction du titre et de l'auteur déterminés, avec gestion des conflits de noms.
        -   `process_epub(...)` : Orchestre l'extraction, l'appel à n8n, le logging et le renommage pour un seul fichier EPUB.
        -   `process_folder(...)` : Itère sur tous les fichiers EPUB d'un dossier (et de ses sous-dossiers), appelant `process_epub` pour chacun.

-   `doc/usage.md` : Détaille l'exécution locale/Docker, la configuration TLS, les variables d'environnement spécifiques à n8n, l'utilisation du mode `--test`, les formats de réponse et la gestion des journaux.
-   `doc/reference.md` : Fournit une référence des arguments de la ligne de commande (CLI) et potentiellement des signatures de fonctions/comportements (à affiner).
-   `README.md` : Aperçu général du projet, arguments principaux de la CLI, fichier `.env`, formats pris en charge, instructions Docker et arborescence du projet.

## Variables d’environnement (principales)

-   `N8N_WEBHOOK_PROD_URL` / `N8N_WEBHOOK_TEST_URL` : URLs des webhooks n8n pour les modes production et test respectivement. `N8N_WEBHOOK_PROD_URL` est utilisé par défaut.
-   `N8N_VERIFY_SSL` : Contrôle la vérification SSL des requêtes HTTP vers n8n.
    -   `false`, `0`, `no`, `non` : Désactive la vérification SSL.
    -   `true`, `1`, `yes`, `oui` (défaut) : Active la vérification SSL.
    -   Tout autre chemin : Spécifie un chemin vers un fichier de certificat CA personnalisé.
-   `N8N_TIMEOUT` : Timeout en secondes pour les requêtes HTTP vers n8n (par défaut `120.0`).
-   `CONFIDENCE_MIN` : Seuil de confiance minimal (float entre 0.0 et 1.0, par défaut `0.9`). Si la confiance renvoyée par n8n est inférieure à cette valeur, le renommage est ignoré. Peut être surchargé par l'argument CLI `--confidence-min`.
-   `EPUB_SOURCE_DIR` : Chemin par défaut du dossier à analyser si non spécifié via `--folder` ou l'invite utilisateur.
-   `EPUB_DEST` : Chemin de destination par défaut pour les EPUB renommés (vide par défaut, ce qui signifie que les fichiers sont renommés sur place).
-   `LOG_DIR` : Répertoire où sera stocké le fichier de log JSONL (par défaut le répertoire courant).
-   `EPUB_LOG_FILE` : Nom du fichier de log JSONL (par défaut `n8n_response.json`).
-   `DEFAULT_MAX_TEXT_CHARS` : Nombre maximal de caractères à extraire du texte de l'EPUB pour l'analyse par n8n (par défaut `4000`).
-   `DEFAULT_SLUG_MAX_LENGTH` : Longueur maximale des slugs générés pour les noms de fichiers (par défaut `150`).


## Comportement CLI

-   `--test` : Active le mode test.
    -   Utilise l'URL de webhook de test (`N8N_WEBHOOK_TEST_URL`).
    -   Affiche la réponse brute du webhook (pas d'exigence de format JSON strict).
    -   N'applique aucun renommage de fichier.
-   `--dry-run` : Simule les renommages. Les fichiers ne sont pas modifiés sur le disque, mais les opérations sont affichées dans la console.
-   `--folder <path>` : Spécifie le dossier à traiter. Surcharge la variable d'environnement `EPUB_SOURCE_DIR` et l'invite utilisateur.
-   `--confidence-min <value>` : Surcharge la variable d'environnement `CONFIDENCE_MIN` pour le seuil de confiance minimal requis pour le renommage.
-   `--limit <n>` : Traite un nombre maximal de `n` fichiers EPUB, puis s'arrête.
-   Sans `--test`, le script exige une réponse JSON structurée de n8n pour pouvoir extraire les informations de renommage.

## Services docker-compose

Le fichier `docker-compose.yml` orchestre les services suivants :

-   **n8n** (`n8nio/n8n:1.119.2`) :
    -   **Port :** `5678` (exposé sur l'hôte).
    -   **Configuration :** Utilise des variables d'environnement pour l'authentification basique (`N8N_BASIC_AUTH_USER`, `N8N_BASIC_AUTH_PASSWORD`), l'hôte (`N8N_HOST`), le protocole HTTPS (`N8N_PROTOCOL`, `N8N_SSL_KEY`, `N8N_SSL_CERT`) et l'URL du webhook.
    -   **Volumes :**
        -   `./n8n_data:/home/node/.n8n` : Persistance des données et workflows de n8n.
        -   `./certs:/certs:ro` : Montage des certificats SSL (en lecture seule) pour la configuration HTTPS.

-   **epub-agent** (construit à partir du `Dockerfile` local) :
    -   **Dépendance :** Démarre après le service `n8n`.
    -   **Variables d'environnement :** Récupère plusieurs variables de l'environnement hôte (ex: `EPUB_ROOT`, `N8N_WEBHOOK_PROD_URL`, `CONFIDENCE_MIN`).
    -   **Chemin d'entrée des EPUB :** Le script recherche les EPUB dans le répertoire `/data` *à l'intérieur* du conteneur.
    -   **Volumes :**
        -   `${EPUB_ROOT:-./ebooks}:/data:rw` : Monte le répertoire local spécifié par `EPUB_ROOT` (par défaut `./ebooks`) dans `/data` du conteneur, permettant à l'agent d'accéder aux fichiers EPUB.
        -   `.:/app:rw` : Monte le répertoire racine du projet local dans `/app` du conteneur, donnant accès au code de l'agent.
        -   `./certs:/certs:ro` : Accès aux certificats pour la validation SSL si `N8N_VERIFY_SSL` est activé.

-   **ollama** (`ollama/ollama:latest`, optionnel) :
    -   **Port :** `11434` (exposé sur l'hôte).
    -   **Accélération GPU :** Configuré pour utiliser les GPU NVIDIA si disponibles (`privileged: true`, `deploy.resources.reservations.devices`).
    -   **Volumes :** `./ollama_data:/root/.ollama` : Persistance des modèles Ollama.
    -   **Entrypoint personnalisé :** Utilise un script `ollama-entrypoint.sh` pour la configuration initiale.
    -   **Profile Docker Compose :** Démarre uniquement si le profil `ollama` est activé (`docker compose --profile ollama up`). Ce service est recommandé pour une installation native pour de meilleures performances.

## Guidelines contribution

-   Les changements doivent être ciblés et cohérents avec le style et l'architecture existants.
-   Lorsqu'une interface change (CLI, formats de payload/réponse n8n, variables d'environnement), il est impératif de mettre à jour simultanément :
    -   `AGENTS.md` (pour les développeurs et agents de code)
    -   `README.md` (aperçu général)
    -   `doc/usage.md` (instructions d'utilisation pour les utilisateurs finaux)
    -   `doc/reference.md` (référence technique détaillée)
-   Éviter d'ajouter des dépendances logicielles lourdes sans discussion préalable.
-   **Tests rapides :**
    -   Exécution locale : `python src/epub_metadata.py --folder <path> --dry-run --limit 5`
    -   Exécution Docker : `docker compose exec epub-agent python src/epub_metadata.py --dry-run --limit 10`
    -   Pour activer le profil `ollama` : `docker compose --profile ollama up -d`
-   **Documentation :** Privilégier des sections brèves, des listes claires, et des exemples de commande exécutables. Assurer la cohérence et la précision en français.
