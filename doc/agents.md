# Agents & automatisations

Ce projet repose sur deux briques principales :

- **n8n** : orchestre l'analyse sémantique via un webhook HTTP. Il reçoit `text`, interroge un modèle et renvoie `titre`, `auteur`, `confiance`, `explication`.
- Les workflows sont versionnés via le dossier monté `n8n_data/` (que vous pouvez committer pour les partager entre machines).
- **Agent de tri EPUB** (ce dépôt) :
  - extrait un extrait pertinent des fichiers EPUB ;
  - envoie ce texte à n8n ;
  - applique les règles métier pour le renommage.
- **Ollama** :
  - conteneur dédié qui héberge les modèles locaux (Mistral 7B pour nos tests) ;
  - lance `ollama serve`, attend qu'il soit disponible puis télécharge `mistral:7b` si nécessaire ;
  - expose l'API sur le port `11434`.

## Flux de bout en bout

1. Le script scanne les dossiers EPUB (localement ou via le conteneur Docker) et lit quelques fichiers HTML internes.
2. Il prépare le texte (nettoyage, limitation à 4 000 caractères) puis appelle le webhook `N8N_WEBHOOK_URL`.
3. n8n répond avec des métadonnées ; selon la confiance, un nouveau nom de fichier est généré et validé.
4. En mode `dry-run`, aucun fichier n'est modifié, ce qui permet de vérifier la sortie avant la phase de production.

## Paramètres clés

| Variable          | Description                                                       |
| ----------------- | ----------------------------------------------------------------- |
| `N8N_WEBHOOK_URL` | URL du webhook exposé par n8n.                                   |
| `EPUB_SOURCE_DIR` | Dossier racine des EPUB lors de l'exécution dans Docker.         |
| `DRY_RUN`         | `true` (défaut) pour simuler, `false` pour renommer réellement.  |
| `CONFIDENCE_MIN`  | `faible`, `moyenne` ou `élevée` pour filtrer les renommages.     |
| `OLLAMA_HOST`     | (Optionnel) URL interne pour consommer Ollama depuis n8n.        |

Ces paramètres peuvent être transmis via Docker, docker-compose ou directement en ligne de commande.
