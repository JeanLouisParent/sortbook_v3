# sortbook_v3

Automatise l'identification et le renommage de fichiers EPUB en s'appuyant sur un workflow n8n.

## Fonctionnalités
- Extraction rapide d'un texte pertinent depuis chaque EPUB.
- Appel HTTP à un webhook n8n qui renvoie titre, auteur, confiance et explication.
- Renommage conditionnel selon le niveau de confiance et la présence d'un titre valide.
- Mode simulation (`dry-run`) pour vérifier les actions avant exécution.

## Structure

```
.
├── docker-compose.yml      # n8n + agent Python + Ollama
├── Dockerfile              # Image du script Python
├── requirements.txt
├── src/epub_metadata.py    # Script principal
└── doc/                    # Documentation (agents, guide d'usage)
```

## Installation rapide

```bash
pip install -r requirements.txt
python src/epub_metadata.py --folder /chemin/vers/ebooks --dry-run
```

Le script peut lire les variables `N8N_WEBHOOK_URL`, `EPUB_SOURCE_DIR`, `DRY_RUN` et `CONFIDENCE_MIN`
depuis l'environnement. Passez `--no-dry-run` ou `DRY_RUN=false` pour renommer réellement.

### Test rapide du webhook

```bash
python src/test_n8n_webhook.py
```

Variables utiles :
- `N8N_WEBHOOK_URL` : change l'URL ciblée.
- `N8N_TEST_TEXT` : texte envoyé (défaut : `test`).

## Docker / Compose

1. Placez vos EPUB dans `./ebooks` (ou un autre dossier).
2. Lancez `docker compose up --build`.
3. Les services disponibles :
   - `n8n` (port 5678) pour le webhook (image officielle taggée 1.119.2, les workflows sont versionnés via le volume `n8n_data/`).
   - `ollama` (port 11434) qui lance automatiquement `ollama serve` et télécharge `mistral:7b` si nécessaire.
   - `epub-agent` qui lit le volume `./ebooks:/data`.

Adaptez les variables dans `docker-compose.yml` selon votre infrastructure.

## Documentation

- `doc/agents.md` : vue d'ensemble des acteurs et variables disponibles.
- `doc/usage.md` : commandes CLI, Docker et docker-compose détaillées.
