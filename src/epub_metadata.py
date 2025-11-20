#!/usr/bin/env python3
"""
EPUB Metadata Helper.

Scans EPUB files, extracts text and metadata, calls n8n webhook,
and optionally renames files based on the response.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import requests


# Configuration defaults
DEFAULT_WEBHOOK_URL = "http://localhost:5678/webhook/epub-metadata"
DEFAULT_TIMEOUT = 120.0
DEFAULT_CONFIDENCE_MIN = 0.9
DEFAULT_MAX_TEXT_CHARS = 4000
DEFAULT_SLUG_MAX_LENGTH = 150

PREFERRED_KEYWORDS = (
    "cover",
    "titlepage",
    "title-page",
    "front",
    "frontmatter",
    "copyright",
)


@dataclass
class Config:
    """Application configuration from environment variables and CLI args."""
    
    webhook_url: str
    verify_ssl: bool | str
    timeout: float
    log_path: Path
    epub_root_label: str
    dest_path: str
    confidence_min: float

    @classmethod
    def load(cls, test_mode: bool = False, confidence_override: float | None = None) -> Config:
        """Load configuration from environment variables."""
        test_url = os.environ.get("N8N_WEBHOOK_TEST_URL")
        prod_url = os.environ.get("N8N_WEBHOOK_PROD_URL")

        if test_mode:
            webhook_url = test_url or DEFAULT_WEBHOOK_URL
        else:
            webhook_url = prod_url or DEFAULT_WEBHOOK_URL

        verify_ssl = cls._parse_ssl_verification()
        timeout = cls._parse_timeout()
        log_path = cls._parse_log_path()
        epub_root_label = os.getcwd()
        dest_path = os.environ.get("EPUB_DEST", "")
        confidence_min = cls._parse_confidence(confidence_override)

        return cls(
            webhook_url=webhook_url,
            verify_ssl=verify_ssl,
            timeout=timeout,
            log_path=log_path,
            epub_root_label=epub_root_label,
            dest_path=dest_path,
            confidence_min=confidence_min,
        )

    @staticmethod
    def _parse_ssl_verification() -> bool | str:
        verify_ssl_raw = os.environ.get("N8N_VERIFY_SSL", "true").strip().lower()
        
        if verify_ssl_raw in {"0", "false", "no", "non"}:
            return False
        elif verify_ssl_raw in {"1", "true", "yes", "oui"}:
            return True
        else:
            return os.environ.get("N8N_VERIFY_SSL", "true").strip()

    @staticmethod
    def _parse_timeout() -> float:
        try:
            return float(os.environ.get("N8N_TIMEOUT", str(DEFAULT_TIMEOUT)))
        except ValueError:
            return DEFAULT_TIMEOUT

    @staticmethod
    def _parse_log_path() -> Path:
        log_dir = Path(os.environ.get("LOG_DIR") or os.getcwd())
        log_filename = os.environ.get("EPUB_LOG_FILE", "n8n_response.json")
        return log_dir / log_filename

    @staticmethod
    def _parse_confidence(override: float | None) -> float:
        if override is not None:
            return override
            
        env_confidence = os.environ.get("CONFIDENCE_MIN")
        if env_confidence is not None:
            try:
                return float(env_confidence.replace(",", "."))
            except ValueError:
                pass
                
        return DEFAULT_CONFIDENCE_MIN


@dataclass
class EpubResult:
    """Result from n8n webhook processing."""
    
    titre: str = "inconnu"
    auteur: str = "inconnu"
    confiance: str = "inconnu"
    explication: str = ""
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EpubResult:
        return cls(
            titre=str(data.get("titre") or "").strip() or "inconnu",
            auteur=str(data.get("auteur") or "").strip() or "inconnu",
            confiance=str(data.get("confiance") or "").strip().lower() or "inconnu",
            explication=str(data.get("explication") or "").strip(),
        )
    
    def get_confidence_value(self) -> float:
        try:
            return float(self.confiance.replace(",", "."))
        except ValueError:
            return -1.0
    
    def should_rename(self, confidence_min: float) -> tuple[bool, str]:
        if self.titre.lower() == "inconnu":
            return False, "Titre inconnu, renommage ignoré."
        
        confidence_value = self.get_confidence_value()
        if confidence_value < confidence_min:
            return False, "Confiance insuffisante pour renommer ce fichier."
        
        return True, ""


@dataclass
class EpubMetadata:
    """Metadata from EPUB OPF file."""
    
    title: str = ""
    creator: str = ""
    publisher: str = ""
    language: str = ""
    identifier: str = ""
    description: str = ""
    
    def to_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "creator": self.creator,
            "publisher": self.publisher,
            "language": self.language,
            "identifier": self.identifier,
            "description": self.description,
        }


class EpubProcessingError(Exception):
    """Base exception for EPUB processing errors."""
    pass


class EpubExtractionError(EpubProcessingError):
    """Error during text or metadata extraction."""
    pass


class WebhookError(EpubProcessingError):
    """Error during n8n webhook communication."""
    pass


def _iter_text_files(zf: zipfile.ZipFile) -> Iterable[zipfile.ZipInfo]:
    """Return EPUB HTML/XHTML files ordered by priority."""
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
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", raw_html, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def extract_text_from_epub(epub_path: Path, max_chars: int = DEFAULT_MAX_TEXT_CHARS) -> str:
    """Extract plain text from EPUB file."""
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
                
                if len(" ".join(texts)) >= max_chars:
                    break
                    
    except (zipfile.BadZipFile, FileNotFoundError):
        return ""

    combined = " ".join(texts).strip()
    return combined[:max_chars]


def extract_metadata_from_epub(epub_path: Path) -> EpubMetadata:
    """Extract metadata from EPUB OPF file."""
    metadata = EpubMetadata()

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

    metadata.title = _get_text(".//dc:title")
    metadata.creator = _get_text(".//dc:creator")
    metadata.publisher = _get_text(".//dc:publisher")
    metadata.language = _get_text(".//dc:language")
    metadata.identifier = _get_text(".//dc:identifier")
    metadata.description = _get_text(".//dc:description")

    return metadata


def _normalize_n8n_response(data: Any) -> dict[str, Any]:
    """Normalize various n8n response formats to a consistent dict."""
    if isinstance(data, dict):
        return data

    if isinstance(data, list) and data:
        first = data[0] or {}
        
        if isinstance(first, dict):
            inner = first.get("output") or first
            
            if isinstance(inner, dict):
                if "title" in inner or "author" in inner:
                    return {
                        "titre": inner.get("title", ""),
                        "auteur": inner.get("author", ""),
                        **{k: v for k, v in inner.items() if k not in ("title", "author")}
                    }
                return inner

    return {}


def call_n8n(payload: dict, config: Config, test_mode: bool = False) -> Optional[dict[str, Any]]:
    """Send data to n8n webhook and return normalized response."""
    try:
        resp = requests.post(
            config.webhook_url,
            json=payload,
            timeout=config.timeout,
            verify=config.verify_ssl,
        )
        resp.raise_for_status()
        
    except requests.RequestException as e:
        error_msg = f"Webhook request failed: {e}"
        print(f"  [Erreur n8n] {error_msg}")
        raise WebhookError(error_msg) from e

    if test_mode:
        print(f"  [n8n/test] Statut HTTP : {resp.status_code}")
        print("  [n8n/test] Réponse brute du webhook :")
        print(resp.text)
        return None

    try:
        data = resp.json()
    except json.JSONDecodeError:
        return {}

    return _normalize_n8n_response(data)


def slugify(text: str, max_length: int = DEFAULT_SLUG_MAX_LENGTH) -> str:
    """Create a safe filename from text."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", cleaned)
    cleaned = cleaned[:max_length]
    cleaned = cleaned.replace(" ", "_")
    return cleaned or "Sans_titre"


def log_result(
    config: Config,
    epub_path: Path,
    result: EpubResult,
    metadata: EpubMetadata,
    payload: dict,
) -> None:
    """Append processing result to log file as JSON line."""
    record = {
        "filename": epub_path.name,
        "path": str(epub_path),
        "titre": result.titre,
        "auteur": result.auteur,
        "confiance": result.confiance,
        "explication": result.explication,
        "destination": config.dest_path,
        "metadata": metadata.to_dict(),
        "payload": payload,
    }

    try:
        config.log_path.parent.mkdir(parents=True, exist_ok=True)
        with config.log_path.open("a", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False)
            f.write("\n")
    except Exception as exc:
        print(f"  [Log] Impossible d'écrire dans {config.log_path}: {exc}")


def rename_epub(epub_path: Path, result: EpubResult, dry_run: bool) -> None:
    """Rename EPUB file based on title and author."""
    if result.auteur.lower() == "inconnu":
        base_name = result.titre
    else:
        base_name = f"{result.auteur} - {result.titre}"

    new_name = slugify(base_name) + ".epub"
    target_path = epub_path.with_name(new_name)
    
    suffix = 1
    while target_path.exists() and target_path != epub_path:
        alt_name = f"{slugify(base_name)} ({suffix}).epub"
        target_path = epub_path.with_name(alt_name)
        suffix += 1

    if dry_run:
        print(f"  [Simulation] Renommerait en : {target_path.name}")
    else:
        try:
            epub_path.rename(target_path)
            print(f"  Fichier renommé en : {target_path.name}")
        except OSError as e:
            print(f"  [Erreur] Impossible de renommer : {e}")


class ConsoleOutput:
    """Helper for consistent console output."""
    
    @staticmethod
    def print_processing(epub_path: Path, index: int, total: int) -> None:
        print(f"[{index}/{total}]")
        print(f"Traitement de : {epub_path}")
    
    @staticmethod
    def print_result(result: EpubResult) -> None:
        print(f"  Titre       : {result.titre}")
        print(f"  Auteur      : {result.auteur}")
        print(f"  Confiance   : {result.confiance}")
        if result.explication:
            print(f"  Explication : {result.explication}")
    
    @staticmethod
    def print_info(message: str) -> None:
        print(f"  {message}")


def process_epub(
    epub_path: Path,
    config: Config,
    dry_run: bool = True,
    test_mode: bool = False,
) -> None:
    """Process a single EPUB file: extract, call n8n, log, and optionally rename."""
    console = ConsoleOutput()
    
    text = extract_text_from_epub(epub_path)
    if not text:
        console.print_info("Aucun texte utile extrait, passage au fichier suivant.")
        return

    metadata = extract_metadata_from_epub(epub_path)

    payload = {
        "filename": epub_path.name,
        "root": config.epub_root_label,
        "destination": config.dest_path,
        "text": text,
        "metadata": metadata.to_dict(),
    }

    try:
        response = call_n8n(payload, config, test_mode=test_mode)
    except WebhookError:
        return

    if test_mode or response is None:
        return

    result = EpubResult.from_dict(response)
    console.print_result(result)
    log_result(config, epub_path, result, metadata, payload)

    should_rename, reason = result.should_rename(config.confidence_min)
    
    if not should_rename:
        console.print_info(reason)
        return

    rename_epub(epub_path, result, dry_run)


def process_folder(
    folder: Path,
    config: Config,
    dry_run: bool = True,
    limit: int | None = None,
    test_mode: bool = False,
) -> None:
    """Recursively process all EPUB files in a folder."""
    console = ConsoleOutput()
    
    if not folder.exists():
        print(f"Dossier introuvable : {folder}")
        return

    files = list(folder.rglob("*.epub"))
    total = len(files)
    
    if not files:
        print("Aucun fichier .epub trouvé dans ce dossier.")
        return

    for idx, epub_file in enumerate(files, start=1):
        console.print_processing(epub_file, idx, total)
        
        process_epub(
            epub_file,
            config,
            dry_run=dry_run,
            test_mode=test_mode,
        )
        
        if limit is not None and idx >= limit:
            break


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extraction et renommage d'EPUB via un workflow n8n.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --folder ~/Books --dry-run
  %(prog)s --folder ~/Books --confidence-min 0.8
  %(prog)s --test --limit 5
        """
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
        default=None,
        help=f"Seuil de confiance minimal (0.0 à 1.0, défaut: {DEFAULT_CONFIDENCE_MIN}).",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule les renommages (aucune modification sur disque).",
    )
    
    parser.add_argument(
        "--test",
        action="store_true",
        help="Utilise le webhook de test (sinon webhook de production).",
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximal de fichiers EPUB à traiter.",
    )
    
    return parser.parse_args()


def main() -> None:
    """Main execution function."""
    args = parse_args()

    config = Config.load(
        test_mode=args.test,
        confidence_override=args.confidence_min
    )

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

    target_folder = target_folder.expanduser()

    process_folder(
        target_folder,
        config,
        dry_run=args.dry_run,
        limit=args.limit,
        test_mode=args.test,
    )

    if args.dry_run:
        print("\nMode simulation : utilisez sans --dry-run pour renommer réellement.")


if __name__ == "__main__":
    main()
