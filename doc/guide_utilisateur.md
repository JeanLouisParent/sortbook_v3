# Guide Utilisateur

Ce guide explique comment installer, configurer et utiliser Sortbook v3, que ce soit en local ou via Docker.

## 1. Configuration (.env)

La configuration se fait principalement via un fichier `.env` à la racine du projet.
Copiez le fichier d'exemple pour commencer :

```bash
cp .env.example .env
```

### Variables Principales

| Variable | Description | Valeur par défaut |
| :--- | :--- | :--- |
| `EPUB_ROOT` | Dossier local contenant vos ebooks (pour Docker) | `./data/ebooks` |
| `EPUB_DEST` | Dossier de destination (pour info dans les logs) | `./data/ebooks_sorted` |
| `N8N_WEBHOOK_PROD_URL` | URL du webhook n8n (Production) | `http://localhost:5678/...` |
| `N8N_VERIFY_SSL` | Vérification SSL (`true`, `false` ou chemin cert) | `true` |

## 2. Installation et Exécution Locale

### Prérequis
- Python 3.9+
- `pip`

### Installation
```bash
make install
# ou
pip install -r requirements.txt
```

### Utilisation
La commande principale est `python src/epub_metadata.py`.

**Exemple : Analyser un dossier**
```bash
python src/epub_metadata.py --folder /mon/dossier/ebooks
```

**Options utiles :**
- `--limit N` : Arrêter après N fichiers (ex: `--limit 5`).
- `--test` : Utiliser le webhook de test n8n et afficher la réponse brute.

## 3. Utilisation avec Docker

Docker Compose permet de lancer n8n, la base de données, et l'agent dans un environnement isolé.

### Démarrer les services
```bash
docker compose up -d
```
Cela lance n8n et la base de données. Accédez à n8n sur `http://localhost:5678` (ou https selon config).

### Lancer l'agent via Docker
Pour exécuter le script d'analyse dans le conteneur :

```bash
docker compose run --rm epub-agent python src/epub_metadata.py --limit 10
```
*Note : Le dossier `/data` dans le conteneur correspond à votre `EPUB_ROOT` local.*

### Certificats SSL (pour n8n HTTPS)
Si vous activez HTTPS pour n8n, placez vos certificats dans le dossier `./certs` :
- `n8n.crt`
- `n8n.key`

Pour le développement local, vous pouvez utiliser `mkcert` pour générer ces certificats.

## 4. Intégration n8n

Le script envoie un JSON au webhook n8n contenant :
- `text`: Extrait du contenu du livre.
- `metadata`: Métadonnées extraites du fichier (titre, auteur, etc.).

### Réponse attendue de n8n
Le workflow n8n fourni renvoie un JSON standardisé (Dublin Core) :

```json
{
  "title": "Le Comte de Monte-Cristo",
  "creator": "Alexandre Dumas",
  "publisher": "Éditeur",
  "description": "Résumé du livre...",
  "language": "fr",
  "date": "1844",
  "identifier": "978..."
}
```

Le script normalise automatiquement ces champs :
- `title` devient `titre`
- `creator` (ou `author`) devient `auteur`
- `description` est conservé

Le script accepte également les clés directes `titre` et `auteur` si vous créez votre propre workflow.

## 5. Dépannage

- **Erreur SSL** : Si vous utilisez un certificat auto-signé, réglez `N8N_VERIFY_SSL=false` dans le `.env` ou pointez vers le certificat CA.
- **Logs** : Les résultats sont enregistrés dans `log/n8n_response.json`.
- **n8n injoignable** : Vérifiez que le conteneur n8n tourne (`docker compose ps`) et que l'URL dans `.env` est correcte.
