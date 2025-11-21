#!/usr/bin/env python3
"""
EPUB Metadata Helper.

Scans EPUB files, extracts text and metadata, calls an n8n webhook,
and logs the normalized response for inspection (sans aucun renommage).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

import requests


# Configuration defaults
DEFAULT_WEBHOOK_URL = "http://localhost:5678/webhook/epub-metadata"
DEFAULT_TIMEOUT = 120.0
DEFAULT_MAX_TEXT_CHARS = 4000

PREFERRED_KEYWORDS = (
    "cover",
    "titlepage",
    "title-page",
    "front",
    "frontmatter",
    "copyright",
)

ISBN_CANDIDATE_RE = re.compile(r"[0-9Xx][0-9Xx\- ]{8,16}[0-9Xx]")


@dataclass
class Config:
    """Application configuration from environment variables and CLI args."""

    webhook_url: str
    verify_ssl: bool | str
    timeout: float
    log_path: Path
    epub_root_label: str
    dest_path: str

    @classmethod
    def load(cls, test_mode: bool = False) -> Config:
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

        return cls(
            webhook_url=webhook_url,
            verify_ssl=verify_ssl,
            timeout=timeout,
            log_path=log_path,
            epub_root_label=epub_root_label,
            dest_path=dest_path,
        )

    @staticmethod
    def _parse_ssl_verification() -> bool | str:
        raw = os.environ.get("N8N_VERIFY_SSL", "true").strip()
        lowered = raw.lower()

        if lowered in {"0", "false", "no", "non"}:
            return False
        if lowered in {"1", "true", "yes", "oui"}:
            return True
        return raw

    @staticmethod
    def _parse_timeout() -> float:
        value = os.environ.get("N8N_TIMEOUT", str(DEFAULT_TIMEOUT))
        try:
            return float(value)
        except ValueError:
            return DEFAULT_TIMEOUT

    @staticmethod
    def _parse_log_path() -> Path:
        log_dir = Path(os.environ.get("LOG_DIR") or os.getcwd())
        log_filename = os.environ.get("EPUB_LOG_FILE", "n8n_response.json")
        return log_dir / log_filename


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


@dataclass
class EpubMetadata:
    """Metadata from EPUB OPF file."""

    title: str = ""
    creator: str = ""
    publisher: str = ""
    language: str = ""
    identifier: str = ""
    description: str = ""
    identifiers: list[str] = field(default_factory=list)
    extra: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "creator": self.creator,
            "publisher": self.publisher,
            "language": self.language,
            "identifier": self.identifier,
            "description": self.description,
            "identifiers": self.identifiers,
            "extra": self.extra,
        }


class EpubProcessingError(Exception):
    """Base exception for EPUB processing errors."""


class EpubExtractionError(EpubProcessingError):
    """Error during text or metadata extraction."""


class WebhookError(EpubProcessingError):
    """Error during n8n webhook communication."""


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


def _normalize_isbn_candidate(candidate: str) -> str:
    """Normalize and validate a potential ISBN-10/13 string.

    - Nettoie les caractères non numériques (hors 'X' final pour ISBN-10).
    - Vérifie la longueur et le checksum.
    - Retourne une chaîne normalisée (sans tirets/espaces) ou "" si invalide.
    """
    cleaned = re.sub(r"[^0-9Xx]", "", candidate).upper()

    if len(cleaned) == 10 and _is_valid_isbn10(cleaned):
        return cleaned
    if len(cleaned) == 13 and _is_valid_isbn13(cleaned):
        return cleaned

    return ""


def _is_valid_isbn10(value: str) -> bool:
    if len(value) != 10 or not re.fullmatch(r"\d{9}[\dX]", value):
        return False

    total = 0
    for index, char in enumerate(value):
        digit = 10 if char == "X" else int(char)
        weight = 10 - index
        total += weight * digit

    return total % 11 == 0


def _is_valid_isbn13(value: str) -> bool:
    if len(value) != 13 or not value.isdigit():
        return False

    total = 0
    for index, char in enumerate(value[:12]):
        digit = int(char)
        total += digit * (1 if index % 2 == 0 else 3)

    check_digit = (10 - (total % 10)) % 10
    return check_digit == int(value[12])


def _find_first_isbn(strings: Iterable[str]) -> Optional[str]:
    """Return the first valid ISBN found in the given strings."""
    for value in strings:
        if not value:
            continue

        for match in ISBN_CANDIDATE_RE.findall(value):
            normalized = _normalize_isbn_candidate(match)
            if normalized:
                return normalized

    return None


def extract_text_from_epub(epub_path: Path, max_chars: int = DEFAULT_MAX_TEXT_CHARS) -> str:
    """Extract plain text from EPUB file."""
    if max_chars == DEFAULT_MAX_TEXT_CHARS:
        env_max = os.environ.get("DEFAULT_MAX_TEXT_CHARS")
        if env_max is not None:
            try:
                max_chars = int(env_max)
            except ValueError:
                max_chars = DEFAULT_MAX_TEXT_CHARS

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


def _extract_full_text(epub_path: Path) -> str:
    """Extract the full plain text from an EPUB (no length limit)."""
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
    except (zipfile.BadZipFile, FileNotFoundError):
        return ""

    return " ".join(texts).strip()


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

    # Collect all dc:identifier values
    for el in root.findall(".//dc:identifier", ns):
        if el.text:
            value = el.text.strip()
            if value:
                metadata.identifiers.append(value)

    if not metadata.identifier and metadata.identifiers:
        metadata.identifier = metadata.identifiers[0]

    # Collect extra <meta> entries and dc:subject as generic metadata
    for el in root.findall(".//{*}meta"):
        key = (el.get("name") or el.get("property") or el.tag).strip()
        value = (el.get("content") or (el.text or "")).strip()
        if not value:
            continue
        metadata.extra.setdefault(key, []).append(value)

    for el in root.findall(".//dc:subject", ns):
        if el.text:
            value = el.text.strip()
            if value:
                metadata.extra.setdefault("subject", []).append(value)

    return metadata


def _normalize_single_n8n_object(obj: dict[str, Any]) -> dict[str, Any]:
    """Normalize a single n8n response object to a consistent dict.

    - If ``title`` / ``author`` are present, they are remapped to ``titre`` / ``auteur``.
    - Existing ``titre`` / ``auteur`` keys are preserved.
    - All other keys are kept as-is.
    """
    data: dict[str, Any] = dict(obj)

    title = data.pop("title", None)
    author = data.pop("author", None)

    if title is not None and not str(data.get("titre", "")).strip():
        data["titre"] = title
    if author is not None and not str(data.get("auteur", "")).strip():
        data["auteur"] = author

    return data


def _normalize_n8n_response(data: Any) -> dict[str, Any]:
    """Normalize various n8n response formats to a consistent dict."""
    if isinstance(data, dict):
        inner = data.get("output") if isinstance(data.get("output"), dict) else data
        return _normalize_single_n8n_object(inner)

    if isinstance(data, list) and data:
        first = data[0] or {}

        if isinstance(first, dict):
            inner = first.get("output") if isinstance(first.get("output"), dict) else first
            if isinstance(inner, dict):
                return _normalize_single_n8n_object(inner)

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
    except requests.RequestException as exc:
        error_msg = f"Webhook request failed: {exc}"
        print(f"  [Erreur n8n] {error_msg}")
        raise WebhookError(error_msg) from exc

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
        with config.log_path.open("a", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False)
            handle.write("\n")
    except Exception as exc:
        print(f"  [Log] Impossible d'écrire dans {config.log_path}: {exc}")


class ConsoleOutput:
    """Helper for consistent console output."""

    @staticmethod
    def print_processing(epub_path: Path, index: int, total: int | None) -> None:
        if total is None:
            print(f"[{index}]")
        else:
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
    test_mode: bool = False,
) -> None:
    """Process a single EPUB file: extract, call n8n, and log the result."""
    console = ConsoleOutput()

    text = extract_text_from_epub(epub_path)
    if not text:
        console.print_info("Aucun texte utile extrait, passage au fichier suivant.")
        return

    metadata = extract_metadata_from_epub(epub_path)

    # 1) Chercher l'ISBN dans les métadonnées
    metadata_strings = [
        metadata.title,
        metadata.creator,
        metadata.publisher,
        metadata.language,
        metadata.identifier,
        metadata.description,
    ]
    isbn = _find_first_isbn(metadata_strings)

    # 2) Si aucun ISBN trouvé, scanner le texte complet
    if isbn is None:
        full_text = _extract_full_text(epub_path)
        isbn = _find_first_isbn([full_text])

    payload = {
        "filename": epub_path.name,
        "isbn": isbn or "",
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


def process_folder(
    folder: Path,
    config: Config,
    limit: int | None = None,
    test_mode: bool = False,
) -> None:
    """Recursively process all EPUB files in a folder."""
    console = ConsoleOutput()

    if not folder.exists():
        print(f"Dossier introuvable : {folder}")
        return

    index = 0

    try:
        for epub_file in folder.rglob("*.epub"):
            index += 1
            console.print_processing(epub_file, index, None)
            process_epub(epub_file, config, test_mode=test_mode)

            if limit is not None and index >= limit:
                break
    except OSError as exc:
        print(f"Erreur lors du parcours du dossier {folder}: {exc}")

    if index == 0:
        print("Aucun fichier .epub trouvé dans ce dossier.")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extraction et analyse d'EPUB via un workflow n8n (sans renommage).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --folder ~/Books --limit 5
  %(prog)s --folder ~/Books --test
        """,
    )

    parser.add_argument(
        "--folder",
        type=Path,
        default=None,
        help="Dossier contenant les EPUB (par défaut : EPUB_SOURCE_DIR ou saisie utilisateur).",
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

    config = Config.load(test_mode=args.test)

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
        limit=args.limit,
        test_mode=args.test,
    )


if __name__ == "__main__":
    main()
