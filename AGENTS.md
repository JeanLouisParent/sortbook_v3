# AGENTS: Architecture, Flux et Guidelines

## Vue d’ensemble

- Composants:
  - n8n: workflow orchestrant l’analyse sémantique (exposé via webhook HTTPS).
  - Agent Python (ce repo): lit les EPUB, extrait texte + métadonnées, appelle n8n, journalise les résultats.
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
3) **Réponse n8n et Normalisation :** n8n effectue son analyse et renvoie une réponse. L'agent Python (via la fonction `_normalize_n8n_response`) est flexible et peut interpréter plusieurs formats de réponse pour en extraire un `EpubResult` (titre, auteur, explication). Les formats gérés incluent :
    *   **Format Dublin Core (utilisé par le workflow fourni) :** `{"title": "...", "creator": "...", "publisher": "...", ...}`.
        *   `title` est mappé vers `titre`.
        *   `creator` est mappé vers `auteur`.
    *   **Format direct :** `{"titre": "...", "auteur": "...", "explication": "..."}`
    *   **Format encapsulé :** `{"output": {"titre": "...", "auteur": "...", ...}}`
    *   **Format liste :** `[{"titre": "...", "auteur": "...", ...}]` ou `[{"output": {"titre": "...", ...}}]`
    En mode `test`, la réponse brute de n8n est affichée et aucune normalisation n'est tentée.
4) **Logging :**
    *   L'agent journalise systématiquement une ligne JSONL par fichier traité dans `EPUB_LOG_FILE`, incluant toutes les données du `payload`, la réponse normalisée de n8n et le chemin de destination.

## Répartition des fichiers

-   `src/epub_metadata.py` (script principal)
    -   **Dataclasses clés :**
        -   `Config` : Gère le chargement de la configuration depuis les variables d'environnement et les arguments CLI. Contient `webhook_url`, `verify_ssl`, `timeout`, `log_path`, `epub_root_label`, `dest_path`.
        -   `EpubResult` : Représente la réponse normalisée de n8n, avec `titre`, `auteur`, `explication`.
        -   `EpubMetadata` : Contient les métadonnées extraites directement du fichier OPF de l'EPUB (`title`, `creator`, `publisher`, `language`, `identifier`, `description`).
    -   **Fonctions clés :**
        -   `extract_text_from_epub(epub_path, max_chars)` : Extrait le texte nettoyé de l'EPUB en priorisant les sections pertinentes (`PREFERRED_KEYWORDS`). Limite l'extraction à `max_chars` (par défaut `DEFAULT_MAX_TEXT_CHARS = 4000`).
        -   `extract_metadata_from_epub(epub_path)` : Lit les métadonnées Dublin Core du fichier OPF de l'EPUB et les renvoie sous forme d'objet `EpubMetadata`.
        -   `call_n8n(payload, config, test_mode)` : Envoie le `payload` JSON à l'URL de webhook n8n configurée. Gère les différents formats de réponse de n8n via `_normalize_n8n_response` pour les convertir en un format `EpubResult` cohérent.
        -   `log_result(...)` : Ajoute un enregistrement JSONL au fichier de log spécifié par `config.log_path`.
        -   `process_epub(...)` : Orchestre l'extraction, l'appel à n8n et le logging pour un seul fichier EPUB.
        -   `process_folder(...)` : Itère sur tous les fichiers EPUB d'un dossier (et de ses sous-dossiers), appelant `process_epub` pour chacun.

-   `doc/guide_utilisateur.md` : Détaille l'exécution locale/Docker, la configuration TLS, les variables d'environnement et l'utilisation.
-   `doc/reference_technique.md` : Référence des arguments CLI, architecture et variables d'environnement.
-   `README.md` : Aperçu général du projet, installation rapide et structure.
-   `pyproject.toml` : Gestion des dépendances et configuration du projet.
-   `Makefile` : Commandes pour installer, tester et nettoyer le projet.

## Variables d’environnement (principales)

-   `N8N_WEBHOOK_PROD_URL` / `N8N_WEBHOOK_TEST_URL` : URLs des webhooks n8n pour les modes production et test respectivement. `N8N_WEBHOOK_PROD_URL` est utilisé par défaut.
-   `N8N_VERIFY_SSL` : Contrôle la vérification SSL des requêtes HTTP vers n8n.
    -   `false`, `0`, `no`, `non` : Désactive la vérification SSL.
    -   `true`, `1`, `yes`, `oui` (défaut) : Active la vérification SSL.
    -   Tout autre chemin : Spécifie un chemin vers un fichier de certificat CA personnalisé.
-   `N8N_TIMEOUT` : Timeout en secondes pour les requêtes HTTP vers n8n (par défaut `120.0`).
-   `EPUB_SOURCE_DIR` : Chemin par défaut du dossier à analyser si non spécifié via `--folder` ou l'invite utilisateur.
-   `EPUB_DEST` : Chemin de destination par défaut (pour info dans les logs).
-   `LOG_DIR` : Répertoire où sera stocké le fichier de log JSONL (par défaut le répertoire courant).
-   `EPUB_LOG_FILE` : Nom du fichier de log JSONL (par défaut `n8n_response.json`).
-   `DEFAULT_MAX_TEXT_CHARS` : Nombre maximal de caractères à extraire du texte de l'EPUB pour l'analyse par n8n (par défaut `4000`).

## Comportement CLI

-   `--test` : Active le mode test.
    -   Utilise l'URL de webhook de test (`N8N_WEBHOOK_TEST_URL`).
    -   Affiche la réponse brute du webhook (pas d'exigence de format JSON strict).
-   `--folder <path>` : Spécifie le dossier à traiter. Surcharge la variable d'environnement `EPUB_SOURCE_DIR` et l'invite utilisateur.
-   `--limit <n>` : Traite un nombre maximal de `n` fichiers EPUB, puis s'arrête.
-   Sans `--test`, le script exige une réponse JSON structurée de n8n pour pouvoir extraire les informations.

## Services docker-compose

Le fichier `docker-compose.yml` orchestre les services suivants :

-   **n8n** (`n8nio/n8n:1.119.2`) :
    -   **Port :** `5678` (exposé sur l'hôte).
    -   **Configuration :** Utilise des variables d'environnement pour l'authentification basique (`N8N_BASIC_AUTH_USER`, `N8N_BASIC_AUTH_PASSWORD`), l'hôte (`N8N_HOST`), le protocole HTTPS (`N8N_PROTOCOL`, `N8N_SSL_KEY`, `N8N_SSL_CERT`) et l'URL du webhook.
    -   **Volumes :**
        -   `./data/n8n_data:/home/node/.n8n` : Persistance des données et workflows de n8n.
        -   `./certs:/certs:ro` : Montage des certificats SSL (en lecture seule) pour la configuration HTTPS.

-   **epub-agent** (construit à partir du `Dockerfile` local) :
    -   **Dépendance :** Démarre après le service `n8n`.
    -   **Variables d'environnement :** Récupère plusieurs variables de l'environnement hôte (ex: `EPUB_ROOT`, `N8N_WEBHOOK_PROD_URL`).
    -   **Chemin d'entrée des EPUB :** Le script recherche les EPUB dans le répertoire `/data` *à l'intérieur* du conteneur.
    -   **Volumes :**
        -   `${EPUB_ROOT:-./data/ebooks}:/data:rw` : Monte le répertoire local spécifié par `EPUB_ROOT` (par défaut `./data/ebooks`) dans `/data` du conteneur, permettant à l'agent d'accéder aux fichiers EPUB.
        -   `.:/app:rw` : Monte le répertoire racine du projet local dans `/app` du conteneur, donnant accès au code de l'agent.
        -   `./certs:/certs:ro` : Accès aux certificats pour la validation SSL si `N8N_VERIFY_SSL` est activé.

-   **ollama** (`ollama/ollama:latest`, optionnel) :
    -   **Port :** `11434` (exposé sur l'hôte).
    -   **Accélération GPU :** Configuré pour utiliser les GPU NVIDIA si disponibles (`privileged: true`, `deploy.resources.reservations.devices`).
    -   **Volumes :** `./data/ollama_data:/root/.ollama` : Persistance des modèles Ollama.
    -   **Entrypoint personnalisé :** Utilise un script `ollama-entrypoint.sh` pour la configuration initiale.
    -   **Profile Docker Compose :** Démarre uniquement si le profil `ollama` est activé (`docker compose --profile ollama up`). Ce service est recommandé pour une installation native pour de meilleures performances.

## Guidelines contribution

-   Les changements doivent être ciblés et cohérents avec le style et l'architecture existants.
-   Lorsqu'une interface change (CLI, formats de payload/réponse n8n, variables d'environnement), il est impératif de mettre à jour simultanément :
    -   `AGENTS.md` (pour les développeurs et agents de code)
    -   `README.md` (aperçu général)
    -   `doc/guide_utilisateur.md` (instructions d'utilisation pour les utilisateurs finaux)
    -   `doc/reference_technique.md` (référence technique détaillée)
-   Éviter d'ajouter des dépendances logicielles lourdes sans discussion préalable.
-   **Tests rapides :**
    -   Exécution locale : `python src/epub_metadata.py --folder <path> --limit 5`
    -   Exécution Docker : `docker compose exec epub-agent python src/epub_metadata.py --limit 10`
    -   Pour activer le profil `ollama` : `docker compose --profile ollama up -d`
-   **Documentation :** Privilégier des sections brèves, des listes claires, et des exemples de commande exécutables. Assurer la cohérence et la précision en français.
