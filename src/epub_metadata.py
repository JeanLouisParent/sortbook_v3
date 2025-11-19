#!/usr/bin/env python3
"""
EPUB metadata helper.

Scans EPUB files, extracts a text snippet + basic OPF metadata,
calls a n8n webhook, prints the result, and optionally renames files.

Configuration is read from environment variables (typically via .env):

- EPUB_ROOT           : host path of the EPUB root folder (used only for payload/log)
- EPUB_SOURCE_DIR     : path inside the container (default: /data)
- EPUB_LOG_FILE       : log path (default: epub_results.log)
- N8N_WEBHOOK_TEST_URL: n8n test webhook URL
- N8N_WEBHOOK_PROD_URL: n8n prod webhook URL
- N8N_VERIFY_SSL      : "true"/"false" or CA path (default: true)
- N8N_TIMEOUT         : HTTP timeout in seconds (default: 120)
- CONFIDENCE_MIN      : default confidence threshold (default: "moyenne")
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Iterable
import zipfile
import xml.etree.ElementTree as ET

import requests


DEFAULT_WEBHOOK_URL = "http://localhost:5678/webhook/epub-metadata"
N8N_WEBHOOK_TEST_URL = os.environ.get("N8N_WEBHOOK_TEST_URL")
N8N_WEBHOOK_PROD_URL = os.environ.get("N8N_WEBHOOK_PROD_URL")
N8N_WEBHOOK_URL = DEFAULT_WEBHOOK_URL

_VERIFY_SSL_RAW = os.environ.get("N8N_VERIFY_SSL", "true").strip()
if _VERIFY_SSL_RAW.lower() in {"0", "false", "no", "non"}:
    VERIFY_SSL: bool | str = False
elif _VERIFY_SSL_RAW.lower() in {"1", "true", "yes", "oui"}:
    VERIFY_SSL = True
else:
    # Any other value is interpreted as a CA bundle / certificate path.
    VERIFY_SSL = _VERIFY_SSL_RAW
try:
    N8N_TIMEOUT = float(os.environ.get("N8N_TIMEOUT", "120"))
except ValueError:
    N8N_TIMEOUT = 120.0
LOG_DIR = Path(os.environ.get("LOG_DIR") or os.getcwd())
LOG_FILENAME = os.environ.get("EPUB_LOG_FILE", "n8n_response.json")
LOG_PATH = LOG_DIR / LOG_FILENAME
EPUB_ROOT_LABEL = os.getcwd()
EPUB_DEST_PATH = os.environ.get("EPUB_DEST", "")

def _parse_confidence(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return default


def _resolve_webhook_url(test_flag: bool) -> str:
    """
    Choose webhook URL based on CLI flag.

    - If --test is passed        -> test webhook (if defined)
    - Otherwise (no --test)      -> prod webhook (if defined)
    - Fallbacks to DEFAULT_WEBHOOK_URL if nothing else is set.
    """
    use_test = test_flag

    if use_test and N8N_WEBHOOK_TEST_URL:
        return N8N_WEBHOOK_TEST_URL
    if not use_test and N8N_WEBHOOK_PROD_URL:
        return N8N_WEBHOOK_PROD_URL

    if use_test:
        return N8N_WEBHOOK_TEST_URL or DEFAULT_WEBHOOK_URL
    return N8N_WEBHOOK_PROD_URL or DEFAULT_WEBHOOK_URL

CONFIDENCE_MIN_DEFAULT = _parse_confidence(os.environ.get("CONFIDENCE_MIN"), 0.9)
PREFERRED_KEYWORDS = (
    "cover",
    "titlepage",
    "title-page",
    "front",
    "frontmatter",
    "copyright",
)


def _iter_text_files(zf: zipfile.ZipFile) -> Iterable[zipfile.ZipInfo]:
    """Return EPUB internal HTML/XHTML files ordered by priority."""
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
    """Remove basic HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", raw_html, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def extract_text_from_epub(epub_path: Path, max_chars: int = 4000) -> str:
    """
    Open the EPUB, read some internal HTML/XHTML files and return plain text.
    If nothing can be read, return an empty string.
    """
    try:
        with zipfile.ZipFile(epub_path) as zf:
            texts: list[str] = []
            for info in _iter_text_files(zf):
                try:
                    with zf.open(info) as handle:
                        raw = handle.read().decode("utf-8", errors="ignore")
                except Exception:
                    continue
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


def extract_metadata_from_epub(epub_path: Path) -> dict:
    """
    Extract some metadata from the internal OPF file (if present).
    Always returns a dict with the same keys (title, creator, publisher, language, identifier, description).
    """
    metadata: dict[str, str] = {
        "title": "",
        "creator": "",
        "publisher": "",
        "language": "",
        "identifier": "",
        "description": "",
    }
    try:
        with zipfile.ZipFile(epub_path) as zf:
            opf_info = next(
                (info for info in zf.infolist() if info.filename.lower().endswith(".opf")),
                None,
            )
            if opf_info is None:
                return metadata

            with zf.open(opf_info) as handle:
                raw_opf = handle.read().decode("utf-8", errors="ignore")
    except (zipfile.BadZipFile, FileNotFoundError, KeyError):
        return metadata

    try:
        root = ET.fromstring(raw_opf)
    except ET.ParseError:
        return metadata

    ns = {"dc": "http://purl.org/dc/elements/1.1/"}

    def _get_text(xpath: str) -> str:
        el = root.find(xpath, ns)
        return (el.text or "").strip() if el is not None and el.text else ""

    metadata["title"] = _get_text(".//dc:title")
    metadata["creator"] = _get_text(".//dc:creator")
    metadata["publisher"] = _get_text(".//dc:publisher")
    metadata["language"] = _get_text(".//dc:language")
    metadata["identifier"] = _get_text(".//dc:identifier")
    metadata["description"] = _get_text(".//dc:description")

    return metadata


def call_n8n(payload: dict, *, test_mode: bool = False) -> dict | None:
    """
    Send data to the n8n webhook and return JSON response.

    In normal mode (hors --test), this helper normalises several formats:
    - dict déjà normalisé avec clés "titre"/"auteur"/... ;
    - liste d’items avec dict "output" ;
    - liste simple [{"title": "...", "author": "..."}] remappée vers titre/auteur.

    En mode test (--test), aucune structure n’est imposée: la réponse brute est
    simplement affichée dans la console et la fonction renvoie None.
    """
    resp = requests.post(
        N8N_WEBHOOK_URL,
        json=payload,
        timeout=N8N_TIMEOUT,
        verify=VERIFY_SSL,
    )
    resp.raise_for_status()

    if test_mode:
        print("  [n8n/test] Statut HTTP :", resp.status_code)
        try:
            print("  [n8n/test] Réponse brute du webhook :")
            print(resp.text)
        except Exception as exc:
            print(f"  [n8n/test] Impossible d'afficher la réponse : {exc}")
        return None

    data = resp.json()

    # Case 1: direct dict with expected keys
    if isinstance(data, dict):
        return data

    # Case 2: list of items
    if isinstance(data, list) and data:
        first = data[0] or {}
        if isinstance(first, dict):
            # 2.a: dict avec "output"
            inner = first.get("output") or first
            if isinstance(inner, dict):
                # 2.b: format simple title/author -> on remappe vers titre/auteur
                if "title" in inner or "author" in inner:
                    return {
                        "titre": inner.get("title", ""),
                        "auteur": inner.get("author", ""),
                    }
                return inner

    # Fallback: return whatever was decoded, the caller will handle missing keys
    return data


def slugify(text: str, max_length: int = 150) -> str:
    """Make a safe filename."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", cleaned)
    cleaned = cleaned[:max_length]
    cleaned = cleaned.replace(" ", "_")
    return cleaned or "Sans_titre"


def log_result(
    epub_path: Path,
    titre: str,
    auteur: str,
    confiance: str,
    explication: str,
    metadata: dict,
    payload: dict,
) -> None:
    """Append a JSON line with the result of one EPUB to the log file."""
    record = {
        "filename": epub_path.name,
        "path": str(epub_path),
        "titre": titre,
        "auteur": auteur,
        "confiance": confiance,
        "explication": explication,
        "destination": EPUB_DEST_PATH,
        "metadata": metadata,
        "payload": payload,
    }
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False)
            f.write("\n")
    except Exception as exc:
        print(f"  [Log] Impossible d'écrire dans {LOG_PATH}: {exc}")


def process_epub(
    epub_path: Path,
    dry_run: bool = True,
    confidence_min: str = "moyenne",
    *,
    test_mode: bool = False,
) -> None:
    """Process a single EPUB: extract, call n8n, log, optionally rename."""
    print(f"Traitement de : {epub_path}")

    text = extract_text_from_epub(epub_path)
    if not text:
        print("  Aucun texte utile extrait, passage au fichier suivant.")
        return

    metadata = extract_metadata_from_epub(epub_path)

    payload = {
        "filename": epub_path.name,
        "root": EPUB_ROOT_LABEL,
        "destination": EPUB_DEST_PATH,
        "text": text,
        "metadata": metadata,
    }

    try:
        result = call_n8n(payload, test_mode=test_mode)
    except Exception as exc:
        print(f"  Erreur lors de l'appel n8n : {exc}")
        return

    # En mode test, on ne traite pas le JSON retourné : l'objectif
    # est seulement d'afficher la réponse brute du webhook.
    if test_mode or result is None:
        return

    titre = str(result.get("titre") or "").strip() or "inconnu"
    auteur = str(result.get("auteur") or "").strip() or "inconnu"
    confiance = str(result.get("confiance") or "").strip().lower() or "inconnu"
    explication = str(result.get("explication") or "").strip()

    print(f"  Titre       : {titre}")
    print(f"  Auteur      : {auteur}")
    print(f"  Confiance   : {confiance}")
    if explication:
        print(f"  Explication : {explication}")

    # Always log, even if we do not rename yet
    log_result(
        epub_path=epub_path,
        titre=titre,
        auteur=auteur,
        confiance=confiance,
        explication=explication,
        metadata=metadata,
        payload=payload,
    )

    # Confidence threshold still uses textual mapping for now
    try:
        confidence_value = float(confiance.replace(",", "."))
    except ValueError:
        confidence_value = -1.0

    if titre.lower() == "inconnu":
        print("  Titre inconnu, renommage ignoré.")
        return
    if confidence_value < confidence_min:
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
    limit: int | None = None,
) -> None:
    """Walk all EPUBs in a folder (recursively) and process them, with optional limit."""
    folder_path = Path(folder).expanduser()
    if not folder_path.exists():
        print(f"Dossier introuvable : {folder_path}")
        return

    files = list(folder_path.rglob("*.epub"))
    total = len(files)
    if not files:
        print("Aucun fichier .epub trouvé dans ce dossier.")
        return

    for idx, epub_file in enumerate(files, start=1):
        print(f"[{idx}/{total}]")
        process_epub(epub_file, dry_run=dry_run, confidence_min=confidence_min)
        if limit is not None and idx >= limit:
            break


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
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
        type=float,
        default=CONFIDENCE_MIN_DEFAULT,
        help="Seuil de confiance minimal (0.0 à 1.0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule les renommages (aucune modification sur disque).",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Utilise le webhook de test (sinon prod selon N8N_MODE).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximal de fichiers EPUB à traiter (par défaut : tous).",
    )
    return parser


def main() -> None:
    """CLI entrypoint."""
    parser = _build_arg_parser()
    args = parser.parse_args()

    global N8N_WEBHOOK_URL
    N8N_WEBHOOK_URL = _resolve_webhook_url(args.test)

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

    process_folder(
        target_folder,
        dry_run=dry_run,
        confidence_min=args.confidence_min,
        limit=args.limit,
    )
    if dry_run:
        print("Mode simulation : passez --no-dry-run ou DRY_RUN=false pour renommer réellement.")


if __name__ == "__main__":
    main()

