# sortbook_v3

Automatise l'identification et le renommage de fichiers EPUB via un workflow n8n et un LLM.

## AperÃ§u
Ce projet permet de traiter automatiquement des fichiers EPUB :
-   **Extraction intelligente :** Extrait du texte pertinent et les mÃ©tadonnÃ©es OPF de chaque EPUB.
-   **Analyse externe :** Envoie ces informations Ã  un workflow n8n (qui peut utiliser un LLM local via Ollama) pour en dÃ©terminer le titre, l'auteur et un indice de confiance.
-   **Renommage conditionnel :** Renomme le fichier si l'indice de confiance est suffisant, sinon, l'opÃ©ration est simplement journalisÃ©e.
-   **Modes d'exÃ©cution :** Supporte un mode `test` pour le dÃ©bogage et un mode `dry-run` pour simuler les renommages.

## Installation rapide (local)

1.  **PrÃ©requis :** Assurez-vous d'avoir Python 3.9+ et `pip` installÃ©s.
2.  **Cloner le dÃ©pÃ´t :**
    ```bash
    git clone https://github.com/votre-utilisateur/sortbook_v3.git
    cd sortbook_v3
    ```
3.  **Installer les dÃ©pendances :**
    ```bash
    pip install -r requirements.txt
    ```
4.  **ExÃ©cuter en mode simulation :**
    ```bash
    python src/epub_metadata.py --folder /chemin/vers/vos/ebooks --dry-run --limit 5
    ```
Le script lit les configurations (URLs de webhook n8n, dossiers source/destination, seuil de confiance, etc.) depuis l'environnement (variables d'environnement ou fichier `.env`). Utilisez `--dry-run` pour simuler les renommages ou omettez-le pour les appliquer rÃ©ellement.
Pour une configuration complÃ¨te avec n8n et Ollama, consultez la section [Docker / Compose](#docker--compose).

## Arguments CLI (principaux)

-   `--folder PATH` : SpÃ©cifie le chemin du dossier contenant les fichiers EPUB Ã  traiter. Si non fourni, le script utilise la variable d'environnement `EPUB_SOURCE_DIR` ou demande Ã  l'utilisateur.
-   `--dry-run` : Active le mode simulation. Le script identifie les EPUB et propose les renommages, mais n'effectue aucune modification sur le disque.
-   `--limit N` : Limite le traitement aux `N` premiers fichiers EPUB trouvÃ©s. Utile pour les tests ou le traitement par lots.
-   `--confidence-min FLOAT` : DÃ©finit le seuil de confiance minimal (de 0.0 Ã  1.0) requis pour qu'un fichier soit renommÃ©. Surcharge la valeur dÃ©finie par la variable d'environnement `CONFIDENCE_MIN`.
-   `--test` : Active le mode test. Le script utilise `N8N_WEBHOOK_TEST_URL` et affiche la rÃ©ponse brute du webhook n8n sans tenter de renommer les fichiers.

Pour plus de dÃ©tails sur le comportement et les interactions avec les variables d'environnement, consultez `AGENTS.md`.

## Configuration (.env)

Les variables d'environnement suivantes sont lues par le script Python et utilisÃ©es par la stack Docker Compose. Vous pouvez les dÃ©finir dans un fichier `.env` Ã  la racine du projet.

```dotenv
# RÃ©pertoires pour les EPUB et les logs
EPUB_ROOT=./ebooks         # Chemin local vers le dossier racine contenant les EPUB. UtilisÃ© par Docker Compose.
EPUB_SOURCE_DIR=/data      # Chemin oÃ¹ le script s'attend Ã  trouver les EPUB Ã  l'intÃ©rieur du conteneur (doit correspondre au montage de EPUB_ROOT).
EPUB_DEST=./Livres_sorted  # Chemin local vers le dossier de destination pour les EPUB renommÃ©s.
LOG_DIR=./log              # RÃ©pertoire oÃ¹ seront stockÃ©s les logs.
EPUB_LOG_FILE=n8n_response.json # Nom du fichier de log.

# Configuration du webhook n8n
N8N_WEBHOOK_TEST_URL=https://192.168.1.56:5678/webhook-test/epub-metadata # URL du webhook pour le mode test.
N8N_WEBHOOK_PROD_URL=https://192.168.1.56:5678/webhook/epub-metadata    # URL du webhook pour le mode production.
N8N_VERIFY_SSL=false       # VÃ©rification SSL : 'true', 'false', ou un chemin vers un fichier de certificat CA (ex: /certs/n8n.crt).
N8N_TIMEOUT=180            # Timeout en secondes pour les requÃªtes HTTP vers n8n.

# ParamÃ¨tres de traitement
CONFIDENCE_MIN=0.9         # Seuil de confiance minimal (float 0.0-1.0) pour le renommage automatique.
DEFAULT_MAX_TEXT_CHARS=4000 # Nombre maximal de caractÃ¨res de texte Ã  extraire de l'EPUB pour l'analyse.
DEFAULT_SLUG_MAX_LENGTH=150 # Longueur maximale pour les noms de fichiers gÃ©nÃ©rÃ©s.
```

**Notes :**
-   Le mode `--test` (argument CLI) force l'utilisation de `N8N_WEBHOOK_TEST_URL`. Sans cet argument, `N8N_WEBHOOK_PROD_URL` est utilisÃ©.
-   Pour `N8N_VERIFY_SSL`, si vous utilisez un chemin de certificat, assurez-vous que le fichier est accessible par le conteneur Docker. `'false'` est pratique pour le dÃ©veloppement local avec des certificats auto-signÃ©s.
-   Les chemins (`EPUB_ROOT`, `EPUB_DEST`, `LOG_DIR`) sont relatifs au dossier racine du projet si spÃ©cifiÃ©s sans chemin absolu.

## Webhook n8n : Formats de rÃ©ponse pris en charge

Le script est conÃ§u pour Ãªtre flexible et peut interprÃ©ter plusieurs formats de rÃ©ponse JSON de votre workflow n8n, grÃ¢ce Ã  la fonction `_normalize_n8n_response`. L'objectif est toujours d'en extraire les informations de renommage (`titre`, `auteur`, `confiance`, `explication`).

Voici les formats de rÃ©ponse que le script peut gÃ©rer :

-   **Format direct (recommandÃ©) :** Un objet JSON contenant directement les clÃ©s souhaitÃ©es.
    ```json
    {
        "titre": "Le Titre du Livre",
        "auteur": "L'Auteur CÃ©lÃ¨bre",
        "confiance": "0.95",
        "explication": "Correspondance Ã©levÃ©e avec la base de donnÃ©es."
    }
    ```
-   **ClÃ©s alternatives `title`/`author` :** Si votre workflow renvoie `title` et `author` au lieu de `titre` et `auteur`, elles seront automatiquement converties.
    ```json
    {
        "title": "The Book Title",
        "author": "Famous Author"
    }
    ```
-   **Format encapsulÃ© (`output`) :** Un objet JSON contenant un sous-objet `output` qui contient lui-mÃªme les informations.
    ```json
    {
        "output": {
            "titre": "Le Titre",
            "auteur": "L'Auteur"
        }
    }
    ```
-   **Format liste :** Le script peut Ã©galement traiter une liste d'objets, en ne considÃ©rant que le premier Ã©lÃ©ment. Ces objets peuvent Ãªtre au format direct ou encapsulÃ©.
    ```json
    [
        { "titre": "Titre 1", "auteur": "Auteur 1" },
        { "titre": "Titre 2", "auteur": "Auteur 2" }
    ]
    ```
    Ou
    ```json
    [
        { "output": { "titre": "Titre", "auteur": "Auteur" } }
    ]
    ```

En mode `--test`, la rÃ©ponse brute de n8n est affichÃ©e directement dans la console sans tentative de normalisation ou de renommage.

## Docker / Compose

Pour une solution complete incluant le serveur n8n, l'agent Python et la base SQLite dans un environnement conteneurise, vous pouvez utiliser Docker Compose. Une option pour Ollama (LLM local) est egalement disponible.

1.  **Configuration du `.env` :**
    Copiez le fichier `.env.example` en `.env` et ajustez les variables d'environnement selon vos besoins, notamment les chemins d'acces (`EPUB_ROOT`, `EPUB_DEST`, `LOG_DIR`) et les URLs de webhook n8n.

2.  **Certificats TLS (pour n8n en HTTPS) :**
    Si vous configurez n8n pour utiliser HTTPS (recommande en production), placez vos fichiers de certificat TLS (par exemple, `n8n.crt` et `n8n.key`) dans le dossier `./certs/`.

3.  **Lancement des services persistants (n8n, SQLite, Ollama optionnel) :**
    Utilisez la commande suivante pour demarrer les services n8n et la base SQLite :
    ```bash
    docker compose up --build -d n8n sqlite
    ```
    Si vous souhaitez egalement inclure le service Ollama (pour un LLM local), utilisez le profil `ollama` :
    ```bash
    docker compose --profile ollama up --build -d
    ```
    L'option `-d` lance les conteneurs en arriere-plan.

4.  **Executer l'agent ponctuellement dans un conteneur :**
    L'agent Python n'a pas vocation a tourner en continu. Il est prevu pour etre lance ponctuellement via `docker compose run` pour traiter un lot d'EPUB, puis s'arreter.

    Par exemple, pour un test rapide en mode simulation et test n8n :
    ```bash
    docker compose run --rm --no-deps \
      -v "${PWD}/src:/app/src:ro" \
      -v "${PWD}/certs:/certs:ro" \
      --entrypoint python \
      epub-agent src/epub_metadata.py --folder /data --limit 4 --dry-run --test
    ```
    Notez que `/data` est le chemin *a l'interieur du conteneur* qui correspond a votre `EPUB_ROOT` local.

Pour plus de details sur la configuration des services Docker, consultez le fichier `docker-compose.yml`.

## Arborescence du projet

- `src/` : Code source de l'agent Python (inclut `epub_metadata.py`)
- `doc/` : Documentation detaillee (`usage.md`, `reference.md`)
- `docker-compose.yml` : Definition des services Docker (n8n, agent, SQLite, Ollama optionnel)
- `Dockerfile` : Image Docker de l'agent Python
- `AGENTS.md` : Notes pour les contributeurs / agents de code
- `.env.example` : Exemple de configuration des variables d'environnement
- `requirements.txt` : Dependances Python
- `README.md` : Vue d'ensemble du projet
