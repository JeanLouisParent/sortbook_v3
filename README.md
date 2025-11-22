# Sortbook v3

**Sortbook** est un outil d'automatisation conçu pour identifier, renommer et trier des fichiers EPUB en utilisant un workflow n8n (enrichi par un LLM).

Il analyse le contenu de vos ebooks, extrait les métadonnées et le texte, interroge une intelligence artificielle pour valider les informations, et organise votre bibliothèque automatiquement.

## 🚀 Fonctionnalités

- **Extraction Intelligente** : Analyse le texte et les métadonnées OPF des fichiers EPUB.
- **Validation par IA** : Utilise un workflow n8n (connecté à un LLM comme Ollama ou OpenAI) pour confirmer le titre et l'auteur.
- **Logging Centralisé** : Enregistre toutes les analyses dans un fichier JSONL pour traitement ultérieur.
- **Dockerisé** : Déploiement facile via Docker Compose incluant n8n et une base de données.

## 📦 Installation

### Prérequis

- Python 3.9+ (pour exécution locale)
- Docker & Docker Compose (pour la stack complète)

### Installation Locale

1.  Clonez le dépôt :
    ```bash
    git clone https://github.com/votre-utilisateur/sortbook_v3.git
    cd sortbook_v3
    ```

2.  Installez les dépendances :
    ```bash
    make install
    # ou
    pip install -r requirements.txt
    ```

3.  Configurez l'environnement :
    ```bash
    cp .env.example .env
    # Éditez .env avec vos paramètres
    ```

## 🛠️ Utilisation Rapide

Pour lancer une analyse sur un dossier d'ebooks :

```bash
python src/epub_metadata.py --folder /chemin/vers/ebooks
```

- `--limit 5` : Ne traite que les 5 premiers fichiers (utile pour tester).

Pour plus de détails, consultez le [Guide Utilisateur](doc/guide_utilisateur.md).

## 📂 Structure du Projet

```
sortbook_v3/
├── data/               # Données (ebooks, n8n, bdd)
├── doc/                # Documentation détaillée
├── src/                # Code source Python
├── tests/              # Tests unitaires
├── workflows/          # Workflows n8n exportés
├── docker-compose.yml  # Orchestration Docker
├── Makefile            # Commandes rapides
└── pyproject.toml      # Configuration du projet
```

## 📚 Documentation

- [Guide Utilisateur](doc/guide_utilisateur.md) : Configuration détaillée, Docker, et utilisation avancée.
- [Référence Technique](doc/reference_technique.md) : Détails sur l'architecture, les arguments CLI et le format des données.
- [Notes pour les Agents](AGENTS.md) : Contexte pour les assistants IA et développeurs.

## 🤝 Contribution

Les contributions sont bienvenues ! Utilisez `make lint` pour vérifier votre code et `make test` pour lancer les tests.
