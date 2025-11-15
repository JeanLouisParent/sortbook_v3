#!/usr/bin/env python3
"""
Script utilitaire pour extraire quelques métadonnées des fichiers EPUB et
les envoyer à un workflow n8n pour identification.

Nécessite le module requests :
    pip install requests
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Iterable
import zipfile

import requests


DEFAULT_WEBHOOK_URL = "http://localhost:5678/webhook/epub-metadata"
# URL du webhook n8n (peut être surchargée par la variable d'environnement N8N_WEBHOOK_URL)
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", DEFAULT_WEBHOOK_URL)

# Fichiers internes prioritaires dans les EPUB
PREFERRED_KEYWORDS = (
    "cover",
    "titlepage",
    "title-page",
    "front",
    "frontmatter",
    "copyright",
)


def _iter_text_files(zf: zipfile.ZipFile) -> Iterable[zipfile.ZipInfo]:
    """Retourne la liste des fichiers texte (html/xhtml) à lire par ordre de priorité."""
    prioritized: list[zipfile.ZipInfo] = []
    fallback: list[zipfile.ZipInfo] = []

    for info in zf.infolist():
        filename = info.filename.lower()
        if not filename.endswith((".xhtml", ".html", ".htm")):
            continue
        if any(keyword in filename for keyword in PREFERRED_KEYWORDS):
            prioritized.append(info)
        else:
            fallback.append(info)

    return prioritized + fallback


def _strip_html(raw_html: str) -> str:
    """Supprime les balises HTML de base et compacte les espaces."""
    text = re.sub(r"<[^>]+>", " ", raw_html, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def extract_text_from_epub(epub_path: Path, max_chars: int = 4000) -> str:
    """
    Ouvre l'EPUB, lit quelques fichiers internes (HTML/XHTML) et retourne du texte brut.
    Si rien n'est trouvé, une chaîne vide est renvoyée.
    """
    try:
        with zipfile.ZipFile(epub_path) as zf:
            texts: list[str] = []
            for info in _iter_text_files(zf):
                try:
                    with zf.open(info) as handle:
                        raw = handle.read().decode("utf-8", errors="ignore")
                except Exception:
                    continue  # Fichier illisible, on passe au suivant
                stripped = _strip_html(raw)
                if stripped:
                    texts.append(stripped)
                joined = " ".join(texts).strip()
                if len(joined) >= max_chars:
                    break
    except (zipfile.BadZipFile, FileNotFoundError):
        return ""

    combined = " ".join(texts).strip()
    return combined[:max_chars]


def call_n8n_for_text(text: str) -> dict:
    """
    Envoie le texte extrait au webhook n8n et retourne la réponse JSON sous forme de dict.
    Lève une exception en cas d'erreur HTTP ou de parsing JSON.
    """
    resp = requests.post(
        N8N_WEBHOOK_URL,
        json={"text": text},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def slugify(text: str, max_length: int = 150) -> str:
    """
    Nettoie une chaîne pour en faire un nom de fichier valide.
    Remplace les caractères interdits et applique une longueur max.
    """
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", cleaned)
    cleaned = cleaned[:max_length]
    cleaned = cleaned.replace(" ", "_")
    return cleaned or "Sans_titre"


def process_epub(
    epub_path: Path,
    dry_run: bool = True,
    confidence_min: str = "moyenne",
) -> None:
    """
    Traite un fichier EPUB :
        - extrait du texte,
        - envoie la demande à n8n,
        - affiche le résultat,
        - renomme éventuellement le fichier si la confiance est suffisante.
    """
    print(f"\nTraitement de : {epub_path}")

    text = extract_text_from_epub(epub_path)
    if not text:
        print("  Aucun texte utile extrait, passage au fichier suivant.")
        return

    try:
        result = call_n8n_for_text(text)
    except Exception as exc:
        print(f"  Erreur lors de l'appel n8n : {exc}")
        return

    titre = (result.get("titre") or "").strip() or "inconnu"
    auteur = (result.get("auteur") or "").strip() or "inconnu"
    confiance = (result.get("confiance") or "").strip().lower() or "inconnu"
    explication = (result.get("explication") or "").strip()

    print(f"  Titre       : {titre}")
    print(f"  Auteur      : {auteur}")
    print(f"  Confiance   : {confiance}")
    if explication:
        print(f"  Explication : {explication}")

    confidence_order = {"faible": 0, "moyenne": 1, "élevée": 2}
    min_threshold = confidence_order.get(confidence_min.lower(), 1)
    confidence_value = confidence_order.get(confiance, -1)

    if titre.lower() == "inconnu":
        print("  Titre inconnu, renommage ignoré.")
        return
    if confidence_value < min_threshold:
        print("  Confiance insuffisante pour renommer ce fichier.")
        return

    if auteur.lower() == "inconnu":
        base_name = titre
    else:
        base_name = f"{auteur} - {titre}"

    new_name = slugify(base_name) + ".epub"
    target_path = epub_path.with_name(new_name)
    suffix = 1
    while target_path.exists():
        alt_name = f"{slugify(base_name)} ({suffix}).epub"
        target_path = epub_path.with_name(alt_name)
        suffix += 1

    if dry_run:
        print(f"  [Simulation] Renommerait en : {target_path.name}")
    else:
        epub_path.rename(target_path)
        print(f"  Fichier renommé en : {target_path.name}")


def process_folder(
    folder: str | Path,
    dry_run: bool = True,
    confidence_min: str = "moyenne",
) -> None:
    """Parcourt tous les EPUB d'un dossier (récursivement) et les traite."""
    folder_path = Path(folder).expanduser()
    if not folder_path.exists():
        print(f"Dossier introuvable : {folder_path}")
        return

    files_found = False
    for epub_file in folder_path.rglob("*.epub"):
        files_found = True
        process_epub(epub_file, dry_run=dry_run, confidence_min=confidence_min)

    if not files_found:
        print("Aucun fichier .epub trouvé dans ce dossier.")


def _env_bool(var_name: str, default: bool) -> bool:
    """Convertit une variable d'environnement en booléen."""
    value = os.environ.get(var_name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "non", "no"}


def _build_arg_parser() -> argparse.ArgumentParser:
    """Construit l'analyseur d'arguments CLI."""
    parser = argparse.ArgumentParser(
        description="Extraction et renommage d'EPUB via un workflow n8n.",
    )
    parser.add_argument(
        "--folder",
        type=Path,
        default=None,
        help="Dossier contenant les EPUB (par défaut : EPUB_SOURCE_DIR ou saisie utilisateur).",
    )
    parser.add_argument(
        "--confidence-min",
        default=os.environ.get("CONFIDENCE_MIN", "moyenne"),
        choices=["faible", "moyenne", "élevée"],
        help="Seuil de confiance minimal pour renommer un fichier.",
    )
    dry_run_default = None  # sera résolu plus tard via env
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=dry_run_default,
        help="Simule les renommages (par défaut).",
    )
    parser.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="Applique réellement les renommages.",
    )
    return parser


def main() -> None:
    """Point d'entrée CLI."""
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.folder is not None:
        target_folder = args.folder
    else:
        env_folder = os.environ.get("EPUB_SOURCE_DIR")
        if env_folder:
            target_folder = Path(env_folder)
        else:
            folder_input = input(
                "Chemin du dossier contenant les EPUB (laisser vide pour le dossier courant) : "
            ).strip()
            target_folder = Path(folder_input or ".")

    dry_run = args.dry_run
    if dry_run is None:
        dry_run = _env_bool("DRY_RUN", default=True)

    process_folder(
        target_folder,
        dry_run=dry_run,
        confidence_min=args.confidence_min,
    )
    if dry_run:
        print("Mode simulation : passez --no-dry-run ou DRY_RUN=false pour renommer réellement.")


if __name__ == "__main__":
    main()
