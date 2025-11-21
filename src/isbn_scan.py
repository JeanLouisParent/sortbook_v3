#!/usr/bin/env python3
"""
ISBN scanner for EPUB files.

Parcourt les EPUB d'un dossier, inspecte les métadonnées ainsi que
l'intégralité du texte et tente d'y détecter des ISBN-10 / ISBN-13.

Usage typique :
    python src/isbn_scan.py --folder ./ebooks --limit 20
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, Set, Tuple

from epub_metadata import (
    extract_metadata_from_epub,
    _iter_text_files,
    _strip_html,
    _normalize_isbn_candidate,
)


ISBN_CANDIDATE_RE = re.compile(r"[0-9Xx][0-9Xx\- ]{8,16}[0-9Xx]")


def _extract_full_text(epub_path: Path) -> str:
    """Extraire l'intégralité du texte utile d'un EPUB (sans limite de longueur)."""
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


def _find_isbns_in_strings(strings: Iterable[str]) -> Set[str]:
    """Trouver des ISBN valides dans une collection de chaînes."""
    found: set[str] = set()

    for value in strings:
        if not value:
            continue

        for match in ISBN_CANDIDATE_RE.findall(value):
            normalized = _normalize_isbn_candidate(match)
            if normalized:
                found.add(normalized)

    return found


def _collect_metadata_strings(epub_path: Path) -> list[str]:
    """Collecter toutes les chaînes de métadonnées susceptibles de contenir un ISBN."""
    meta = extract_metadata_from_epub(epub_path)

    strings: list[str] = [
        meta.title,
        meta.creator,
        meta.publisher,
        meta.language,
        meta.identifier,
        meta.description,
    ]

    strings.extend(meta.identifiers)

    for key, values in meta.extra.items():
        strings.append(key)
        strings.extend(values)

    return [s for s in strings if s]


def scan_epub_for_isbn(epub_path: Path) -> Tuple[bool, bool]:
    """Scanner un EPUB et indiquer si un ISBN est trouvé.

    On cherche d'abord dans les métadonnées ; si au moins un ISBN est
    trouvé, on ne scanne pas le texte (optimisation, même logique que l'agent principal).
    """
    metadata_strings = _collect_metadata_strings(epub_path)
    metadata_isbns = _find_isbns_in_strings(metadata_strings)

    if metadata_isbns:
        return True, False

    text = _extract_full_text(epub_path)
    text_isbns = _find_isbns_in_strings([text])

    return False, bool(text_isbns)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan d'ISBN dans les EPUB (métadonnées + texte complet).",
    )

    parser.add_argument(
        "--folder",
        type=Path,
        required=True,
        help="Dossier contenant les fichiers EPUB à analyser.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Nombre maximal de fichiers EPUB à analyser.",
    )

    return parser.parse_args()


def _print_progress_block(
    done: int,
    total_to_process: int,
    percent: float,
    eta_hours: int,
    eta_minutes: int,
    meta_count: int,
    text_count: int,
    none_count: int,
) -> None:
    """Afficher le bloc de progression (et le rafraîchir sur place)."""
    meta_pct = (meta_count / done * 100) if done else 0.0
    text_pct = (text_count / done * 100) if done else 0.0
    none_pct = (none_count / done * 100) if done else 0.0

    bar_width = 30
    filled = int(bar_width * done / total_to_process) if total_to_process else 0
    bar = "#" * filled + "-" * (bar_width - filled)

    header_line = f"Livres traités : {done} / {total_to_process}"
    bar_line = f"[{bar}] {percent:5.1f}%  ETA {eta_hours}h{eta_minutes:02d}m"
    meta_line = f"  META  : {meta_count:,} ({meta_pct:4.1f}%)"
    text_line = f"  TEXTE : {text_count:,} ({text_pct:4.1f}%)"
    none_line = f"  AUCUN : {none_count:,} ({none_pct:4.1f}%)"

    if done > 1:
        # Remonter et effacer les 5 lignes précédentes (header + 4 lignes)
        for _ in range(5):
            sys.stdout.write("\x1b[1A\x1b[2K\r")

    sys.stdout.write(header_line + "\n")
    sys.stdout.write(bar_line + "\n")
    sys.stdout.write(meta_line + "\n")
    sys.stdout.write(text_line + "\n")
    sys.stdout.write(none_line + "\n")
    sys.stdout.flush()


def main() -> None:
    args = parse_args()
    folder: Path = args.folder.expanduser()

    if not folder.exists():
        print(f"Dossier introuvable : {folder}")
        return

    files = list(folder.rglob("*.epub"))
    if not files:
        print("Aucun fichier .epub trouvé dans ce dossier.")
        return

    total = len(files)
    if args.limit is not None:
        total_to_process = min(total, args.limit)
    else:
        total_to_process = total

    meta_count = 0
    text_count = 0
    none_count = 0

    start_time = time.time()

    target_files = files[:total_to_process]
    max_workers = min(4, total_to_process) or 1
    processed = 0

    if not target_files:
        print("Limite de fichiers à 0 ; aucun scan exécuté.")
        return

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_epub_for_isbn, epub_file): epub_file for epub_file in target_files}

        for future in as_completed(futures):
            has_meta, has_text = future.result()

            if has_meta:
                meta_count += 1
            if has_text:
                text_count += 1
            if not has_meta and not has_text:
                none_count += 1

            processed += 1
            done = processed
            elapsed = time.time() - start_time
            remaining = max(total_to_process - done, 0)
            eta_seconds = (elapsed / done * remaining) if done > 0 else 0.0
            eta_hours = int(eta_seconds // 3600)
            eta_minutes = int((eta_seconds % 3600) // 60)
            percent = (done / total_to_process * 100) if total_to_process else 0.0

            _print_progress_block(
                done=done,
                total_to_process=total_to_process,
                percent=percent,
                eta_hours=eta_hours,
                eta_minutes=eta_minutes,
                meta_count=meta_count,
                text_count=text_count,
                none_count=none_count,
            )

    print()  # retour ligne final pour ne pas écraser le résumé

    final_meta_pct = (meta_count / total_to_process * 100) if total_to_process else 0.0
    final_text_pct = (text_count / total_to_process * 100) if total_to_process else 0.0
    final_none_pct = (none_count / total_to_process * 100) if total_to_process else 0.0

    print("Résumé du scan ISBN :")
    print(f"  Fichiers analysés      : {total_to_process}")
    print(f"  ISBN trouvés metadata  : {meta_count} ({final_meta_pct:4.1f}%)")
    print(f"  ISBN trouvés texte     : {text_count} ({final_text_pct:4.1f}%)")
    print(f"  Aucun ISBN détecté     : {none_count} ({final_none_pct:4.1f}%)")


if __name__ == "__main__":
    main()

