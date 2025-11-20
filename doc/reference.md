# Référence technique

## Arguments CLI

Le script `epub_metadata.py` accepte les arguments suivants :

-   `--folder PATH` : Chemin du dossier contenant les fichiers EPUB à traiter. Si non spécifié, le script utilise la variable d'environnement `EPUB_SOURCE_DIR` ou demande à l'utilisateur.
-   `--confidence-min FLOAT` : Seuil de confiance minimal (float entre 0.0 et 1.0) pour le renommage automatique. Surcharge la valeur définie par la variable d'environnement `CONFIDENCE_MIN`.
-   `--dry-run` : Active le mode simulation. Les opérations de renommage sont affichées dans la console mais aucune modification n'est effectuée sur le disque.
-   `--test` : Active le mode test. Le script utilise l'URL de test n8n (`N8N_WEBHOOK_TEST_URL`), affiche la réponse brute du webhook et n'effectue aucun renommage.
-   `--limit N` : Limite le traitement aux `N` premiers fichiers EPUB trouvés.

Pour des exemples d'utilisation et une description plus détaillée, consultez la section "Arguments CLI (principaux)" du `README.md`.

## Fonctions principales (`src/epub_metadata.py`)

### Dataclasses
-   `Config`: Classe de configuration de l'application, chargée à partir des variables d'environnement et des arguments CLI.
-   `EpubResult`: Représente le résultat normalisé de la réponse du webhook n8n (titre, auteur, confiance, explication) et contient la logique de décision de renommage.
-   `EpubMetadata`: Contient les métadonnées extraites directement du fichier OPF de l'EPUB.

### Fonctions
-   `extract_text_from_epub(epub_path: Path, max_chars: int = DEFAULT_MAX_TEXT_CHARS) -> str`
    -   Ouvre l'EPUB, priorise les fichiers HTML/XHTML pertinents (couverture, page de titre...), nettoie le texte des balises HTML et renvoie un extrait limité à `max_chars` caractères.

-   `extract_metadata_from_epub(epub_path: Path) -> EpubMetadata`
    -   Parse le fichier OPF interne de l'EPUB et en extrait les métadonnées Dublin Core (`title`, `creator`, `publisher`, `language`, `identifier`, `description`) sous forme d'objet `EpubMetadata`.

-   `call_n8n(payload: dict, config: Config, test_mode: bool = False) -> Optional[dict[str, Any]]`
    -   Envoie le `payload` JSON au webhook n8n spécifié par `config.webhook_url`.
    -   Gère les erreurs de requête (`requests.RequestException`).
    -   En mode `test_mode=True` : Affiche la réponse brute du webhook et renvoie `None`.
    -   En mode normal : Normalise la réponse JSON de n8n via `_normalize_n8n_response` pour un format cohérent (`dict` avec `titre`, `auteur`, `confiance`, `explication`). Se référer à `AGENTS.md` pour les formats de réponse n8n pris en charge.

-   `process_epub(epub_path: Path, config: Config, dry_run: bool = True, test_mode: bool = False) -> None`
    -   Orchestre le traitement d'un unique fichier EPUB : extrait le texte et les métadonnées, construit le `payload`, appelle `call_n8n`, loggue le résultat et, en mode normal et si la confiance est suffisante, propose/effectue le renommage.

-   `process_folder(folder: Path, config: Config, dry_run: bool = True, limit: int | None = None, test_mode: bool = False) -> None`
    -   Itère de manière récursive sur tous les fichiers `.epub` dans le `folder` donné et appelle `process_epub` pour chacun.
    -   Respecte l'argument `limit` si fourni pour traiter un nombre maximal de fichiers.

### Fonctions utilitaires
-   `slugify(text: str, max_length: int = DEFAULT_SLUG_MAX_LENGTH) -> str`: Nettoie une chaîne de caractères pour en faire un nom de fichier sûr et valide.
-   `log_result(...)`: Ajoute une entrée JSONL au fichier de log après le traitement d'un EPUB.

## Variables d’environnement

Les variables d'environnement sont lues au démarrage du script et peuvent être définies via le système, un fichier `.env`, ou surchargées par les arguments de ligne de commande.

-   `N8N_WEBHOOK_PROD_URL` : URL du webhook n8n de production.
-   `N8N_WEBHOOK_TEST_URL` : URL du webhook n8n de test (utilisée avec l'option `--test`).
-   `N8N_VERIFY_SSL` : Contrôle la vérification SSL des requêtes HTTP vers n8n. Peut être `false` (désactivé), `true` (activé, par défaut), ou un chemin vers un fichier de certificat CA (`/certs/n8n.crt`).
-   `N8N_TIMEOUT` : Délai maximum en secondes pour l'appel HTTP au webhook (par défaut `120.0`).
-   `EPUB_SOURCE_DIR` : Chemin par défaut du dossier source des EPUB.
-   `EPUB_DEST` : Chemin par défaut du dossier de destination des EPUB renommés.
-   `LOG_DIR` : Répertoire où sera créé le fichier de log JSONL.
-   `EPUB_LOG_FILE` : Nom du fichier de log JSONL.
-   `CONFIDENCE_MIN` : Seuil de confiance minimal (float 0.0-1.0) pour le renommage. Peut être surchargé par `--confidence-min`.
-   `DEFAULT_MAX_TEXT_CHARS` : Nombre maximal de caractères à extraire de l'EPUB pour l'analyse (par défaut `4000`).
-   `DEFAULT_SLUG_MAX_LENGTH` : Longueur maximale pour les slugs générés pour les noms de fichiers (par défaut `150`).

Pour une configuration complète et des exemples, veuillez consulter le `README.md` et `doc/usage.md`.

