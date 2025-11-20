# sortbook_v3

Automatise l'identification et le renommage de fichiers EPUB via un workflow n8n et un LLM.

## Aperçu
Ce projet permet de traiter automatiquement des fichiers EPUB :
-   **Extraction intelligente :** Extrait du texte pertinent et les métadonnées OPF de chaque EPUB.
-   **Analyse externe :** Envoie ces informations à un workflow n8n (qui peut utiliser un LLM local via Ollama) pour en déterminer le titre, l'auteur et un indice de confiance.
-   **Renommage conditionnel :** Renomme le fichier si l'indice de confiance est suffisant, sinon, l'opération est simplement journalisée.
-   **Modes d'exécution :** Supporte un mode `test` pour le débogage et un mode `dry-run` pour simuler les renommages.

## Installation rapide (local)

1.  **Prérequis :** Assurez-vous d'avoir Python 3.9+ et `pip` installés.
2.  **Cloner le dépôt :**
    ```bash
    git clone https://github.com/votre-utilisateur/sortbook_v3.git
    cd sortbook_v3
    ```
3.  **Installer les dépendances :**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Exécuter en mode simulation :**
    ```bash
    python src/epub_metadata.py --folder /chemin/vers/vos/ebooks --dry-run --limit 5
    ```
Le script lit les configurations (URLs de webhook n8n, dossiers source/destination, seuil de confiance, etc.) depuis l'environnement (variables d'environnement ou fichier `.env`). Utilisez `--dry-run` pour simuler les renommages ou omettez-le pour les appliquer réellement.
Pour une configuration complète avec n8n et Ollama, consultez la section [Docker / Compose](#docker--compose).

## Arguments CLI (principaux)

-   `--folder PATH` : Spécifie le chemin du dossier contenant les fichiers EPUB à traiter. Si non fourni, le script utilise la variable d'environnement `EPUB_SOURCE_DIR` ou demande à l'utilisateur.
-   `--dry-run` : Active le mode simulation. Le script identifie les EPUB et propose les renommages, mais n'effectue aucune modification sur le disque.
-   `--limit N` : Limite le traitement aux `N` premiers fichiers EPUB trouvés. Utile pour les tests ou le traitement par lots.
-   `--confidence-min FLOAT` : Définit le seuil de confiance minimal (de 0.0 à 1.0) requis pour qu'un fichier soit renommé. Surcharge la valeur définie par la variable d'environnement `CONFIDENCE_MIN`.
-   `--test` : Active le mode test. Le script utilise `N8N_WEBHOOK_TEST_URL` et affiche la réponse brute du webhook n8n sans tenter de renommer les fichiers.

Pour plus de détails sur le comportement et les interactions avec les variables d'environnement, consultez `AGENTS.md`.

## Configuration (.env)

Les variables d'environnement suivantes sont lues par le script Python et utilisées par la stack Docker Compose. Vous pouvez les définir dans un fichier `.env` à la racine du projet.

```dotenv
# Répertoires pour les EPUB et les logs
EPUB_ROOT=./ebooks         # Chemin local vers le dossier racine contenant les EPUB. Utilisé par Docker Compose.
EPUB_SOURCE_DIR=/data      # Chemin où le script s'attend à trouver les EPUB à l'intérieur du conteneur (doit correspondre au montage de EPUB_ROOT).
EPUB_DEST=./Livres_sorted  # Chemin local vers le dossier de destination pour les EPUB renommés.
LOG_DIR=./log              # Répertoire où seront stockés les logs.
EPUB_LOG_FILE=n8n_response.json # Nom du fichier de log.

# Configuration du webhook n8n
N8N_WEBHOOK_TEST_URL=https://192.168.1.56:5678/webhook-test/epub-metadata # URL du webhook pour le mode test.
N8N_WEBHOOK_PROD_URL=https://192.168.1.56:5678/webhook/epub-metadata    # URL du webhook pour le mode production.
N8N_VERIFY_SSL=false       # Vérification SSL : 'true', 'false', ou un chemin vers un fichier de certificat CA (ex: /certs/n8n.crt).
N8N_TIMEOUT=180            # Timeout en secondes pour les requêtes HTTP vers n8n.

# Paramètres de traitement
CONFIDENCE_MIN=0.9         # Seuil de confiance minimal (float 0.0-1.0) pour le renommage automatique.
DEFAULT_MAX_TEXT_CHARS=4000 # Nombre maximal de caractères de texte à extraire de l'EPUB pour l'analyse.
DEFAULT_SLUG_MAX_LENGTH=150 # Longueur maximale pour les noms de fichiers générés.
```

**Notes :**
-   Le mode `--test` (argument CLI) force l'utilisation de `N8N_WEBHOOK_TEST_URL`. Sans cet argument, `N8N_WEBHOOK_PROD_URL` est utilisé.
-   Pour `N8N_VERIFY_SSL`, si vous utilisez un chemin de certificat, assurez-vous que le fichier est accessible par le conteneur Docker. `'false'` est pratique pour le développement local avec des certificats auto-signés.
-   Les chemins (`EPUB_ROOT`, `EPUB_DEST`, `LOG_DIR`) sont relatifs au dossier racine du projet si spécifiés sans chemin absolu.

## Webhook n8n : Formats de réponse pris en charge

Le script est conçu pour être flexible et peut interpréter plusieurs formats de réponse JSON de votre workflow n8n, grâce à la fonction `_normalize_n8n_response`. L'objectif est toujours d'en extraire les informations de renommage (`titre`, `auteur`, `confiance`, `explication`).

Voici les formats de réponse que le script peut gérer :

-   **Format direct (recommandé) :** Un objet JSON contenant directement les clés souhaitées.
    ```json
    {
        "titre": "Le Titre du Livre",
        "auteur": "L'Auteur Célèbre",
        "confiance": "0.95",
        "explication": "Correspondance élevée avec la base de données."
    }
    ```
-   **Clés alternatives `title`/`author` :** Si votre workflow renvoie `title` et `author` au lieu de `titre` et `auteur`, elles seront automatiquement converties.
    ```json
    {
        "title": "The Book Title",
        "author": "Famous Author"
    }
    ```
-   **Format encapsulé (`output`) :** Un objet JSON contenant un sous-objet `output` qui contient lui-même les informations.
    ```json
    {
        "output": {
            "titre": "Le Titre",
            "auteur": "L'Auteur"
        }
    }
    ```
-   **Format liste :** Le script peut également traiter une liste d'objets, en ne considérant que le premier élément. Ces objets peuvent être au format direct ou encapsulé.
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

En mode `--test`, la réponse brute de n8n est affichée directement dans la console sans tentative de normalisation ou de renommage.

## Docker / Compose

Pour une solution complète incluant le serveur n8n et l'agent Python dans un environnement conteneurisé, vous pouvez utiliser Docker Compose. Une option pour Ollama (LLM local) est également disponible.

1.  **Configuration du `.env` :**
    Copiez le fichier `.env.example` en `.env` et ajustez les variables d'environnement selon vos besoins, notamment les chemins d'accès (`EPUB_ROOT`, `EPUB_DEST`, `LOG_DIR`) et les URLs de webhook n8n.

2.  **Certificats TLS (pour n8n en HTTPS) :**
    Si vous configurez n8n pour utiliser HTTPS (recommandé en production), placez vos fichiers de certificat TLS (par exemple, `n8n.crt` et `n8n.key`) dans le dossier `./certs/`.

3.  **Lancement des services :**
    Utilisez la commande suivante pour démarrer les services n8n et `epub-agent` :
    ```bash
    docker compose up --build -d
    ```
    Si vous souhaitez également inclure le service Ollama (pour un LLM local), utilisez le profil `ollama` :
    ```bash
    docker compose --profile ollama up --build -d
    ```
    L'option `-d` lance les conteneurs en arrière-plan.

4.  **Tester le script dans le conteneur :**
    Pour exécuter le script `epub-agent` à l'intérieur du conteneur (par exemple, pour des tests ou un traitement manuel) :
    ```bash
    docker compose exec epub-agent \
      python src/epub_metadata.py --folder /data --limit 10 --dry-run
    ```
    Notez que `/data` est le chemin *à l'intérieur du conteneur* qui correspond à votre `EPUB_ROOT` local.

Pour plus de détails sur la configuration des services Docker, consultez le fichier `docker-compose.yml`.

## Arborescence du projet

```
.
├── src/                          # Code source de l'agent Python
│  ├── epub_metadata.py           # Script principal de traitement des EPUB
│  └── test_n8n_webhook.py        # Script de test rapide pour le webhook n8n
├── doc/                          # Documentation détaillée
│  ├── usage.md                   # Guide d'utilisation pour les utilisateurs finaux (inclut n8n, modes de fonctionnement)
│  ├── reference.md               # Référence technique (CLI, fonctions, etc.)
│  └── ai_prompt.md               # Exemples de prompts pour l'IA (si utilisé dans n8n)
├── docker-compose.yml            # Définition des services Docker (n8n, agent Python, Ollama optionnel)
├── Dockerfile                    # Instructions pour construire l'image Docker de l'agent Python
├── AGENTS.md                     # Documentation technique pour les développeurs et agents de code
├── .env.example                  # Exemple de fichier de configuration pour les variables d'environnement
├── requirements.txt              # Dépendances Python
└── README.md                     # Vue d'ensemble du projet
```

