import os
import logging
import io
from typing import Set, Optional
from webdav3.client import Client
from webdav3.exceptions import WebDavException, ResponseErrorCode

from src.webdav.file_comparator import (
    FileComparator,
    ComparisonStrategy,
    FileComparisonResult
)
from src.webdav.conflict_handler import (
    ConflictHandler,
    ConflictResolution
)

log = logging.getLogger(__name__)


def _get_extension(path: str) -> str:
    _, extension = os.path.splitext(path)
    return extension


def _join_remote(base: str, child: str) -> str:
    return base.rstrip('/') + '/' + child.lstrip('/')


class WebDavDownloader:
    def __init__(
            self,
            client: Client,
            skipables_file: str = 'skipables.txt',
            comparison_strategy: str = 'hybrid',
            conflict_resolution: str = 'overwrite',
            backup_before_overwrite: bool = False,
            quarantine_path: str = 'conflicts',
            mtime_tolerance_seconds: int = 60
    ):
        self._client = client
        self._skipables_file = skipables_file
        self._skip_set = self._load_skipables()

        # Vergleichsstrategie
        strategy_map = {
            'fast': ComparisonStrategy.FAST,
            'safe': ComparisonStrategy.SAFE,
            'hybrid': ComparisonStrategy.HYBRID
        }
        strategy = strategy_map.get(comparison_strategy.lower(), ComparisonStrategy.HYBRID)
        self._comparator = FileComparator(strategy, mtime_tolerance_seconds)

        # Konfliktbehandlung
        resolution_map = {
            'overwrite': ConflictResolution.OVERWRITE,
            'skip': ConflictResolution.SKIP,
            'keep_both': ConflictResolution.KEEP_BOTH,
            'quarantine': ConflictResolution.QUARANTINE
        }
        resolution = resolution_map.get(conflict_resolution.lower(), ConflictResolution.OVERWRITE)
        self._conflict_handler = ConflictHandler(resolution, backup_before_overwrite, quarantine_path)

    def _load_skipables(self) -> Set[str]:
        try:
            with open(self._skipables_file, 'r', encoding='utf-8') as f:
                return {line.strip() for line in f if line.strip()}
        except FileNotFoundError:
            return set()

    def download_file(self, remote_path: str, local_path: str, exclude_extensions: list[str]) -> bool:
        if _get_extension(remote_path) in exclude_extensions:
            return False

        os.makedirs(os.path.dirname(local_path) if os.path.dirname(local_path) else '.', exist_ok=True)

        # Prüfe ob lokale Datei existiert und hole Remote-Info
        local_exists = os.path.exists(local_path)
        remote_info = None

        if local_exists:
            try:
                remote_info = self._client.info(remote_path)
            except (ResponseErrorCode, WebDavException) as e:
                log.warning(f"Konnte Remote-Info nicht abrufen für {remote_path}: {e}")
                # Fallback: einfach herunterladen
                return self._perform_download(remote_path, local_path)

        # Vergleich durchführen wenn lokale Datei existiert
        if local_exists and remote_info:
            comparison_result = self._comparator.compare_files(local_path, remote_info)

            if comparison_result.files_identical:
                log.debug(f"Dateien identisch, überspringe Download: {local_path}")
                return True

            # Bei SAFE-Strategie oder Verdacht in HYBRID: Hash-Vergleich durchführen
            if (self._comparator.strategy == ComparisonStrategy.SAFE or
                    (self._comparator.strategy == ComparisonStrategy.HYBRID and comparison_result.suspicion_reason)):
                hash_result = self._compare_with_hash(remote_path, local_path, remote_info)
                if hash_result and hash_result.files_identical:
                    log.debug(f"Dateien identisch (Hash-Vergleich), überspringe Download: {local_path}")
                    # Nur mtime anpassen wenn gewünscht (optional)
                    return True
                comparison_result = hash_result if hash_result else comparison_result

            # Konfliktbehandlung
            should_download = self._conflict_handler.handle_conflict(
                local_path, remote_path, comparison_result
            )

            if not should_download:
                return True  # Datei wurde übersprungen, aber das ist erfolgreich

        # Download durchführen
        return self._perform_download(remote_path, local_path)

    def _compare_with_hash(
            self,
            remote_path: str,
            local_path: str,
            remote_info: dict
    ) -> Optional[FileComparisonResult]:
        """Führt Hash-Vergleich durch (lädt Datei temporär in Memory)"""
        try:
            # Lade Remote-Datei in Memory-Stream
            remote_stream = self._client.download_iter(remote_path)
            if remote_stream:
                # Konvertiere Generator zu BytesIO für Hash-Berechnung
                content_bytes = b''.join(remote_stream)
                stream_io = io.BytesIO(content_bytes)

                result = self._comparator.compare_with_hash(
                    local_path, remote_path, remote_info, stream_io
                )

                return result
        except Exception as e:
            log.warning(f"Hash-Vergleich fehlgeschlagen für {remote_path}: {e}")

        return None

    def _perform_download(self, remote_path: str, local_path: str) -> bool:
        """Führt den eigentlichen Download durch"""
        try:
            self._client.download_sync(remote_path=remote_path, local_path=local_path)

            # Bei QUARANTINE-Strategie: Datei nach Download in Quarantäne verschieben
            if self._conflict_handler.resolution == ConflictResolution.QUARANTINE:
                self._conflict_handler.move_to_quarantine_after_download(local_path, remote_path)

            return True
        except ResponseErrorCode as e:
            if getattr(e, 'code', None) == 403:
                log.error(f'Keine Leserechte: {remote_path}')
                self._add_to_skipables(remote_path)
            else:
                log.error(f'HTTP-Fehler {getattr(e, "code", "?")}: {remote_path} -> {e}')
            return False
        except WebDavException as e:
            log.error(f'WebDAV-Fehler: {remote_path} -> {e}')
            return False

    def _add_to_skipables(self, remote_path: str) -> None:
        try:
            with open(self._skipables_file, 'a', encoding='utf-8') as f:
                f.write(remote_path + '\n')
            self._skip_set.add(remote_path)
        except (FileNotFoundError, PermissionError, OSError) as e:
            log.warning(f'Konnte nicht zu skipables hinzufügen: {e}')

    def pull_continue(
            self,
            remote_dir: str,
            local_dir: str,
            use_skipables: bool,
            exclude_extensions: list[str]
    ) -> None:
        os.makedirs(local_dir, exist_ok=True)

        entries = self._client.list(remote_dir)
        remote_basename = remote_dir.rstrip('/').split('/')[-1]

        for name in entries:
            if name in ('', '.', '..'):
                continue

            name_clean = name.rstrip('/')

            if name_clean == remote_basename:
                continue

            remote_path = _join_remote(remote_dir, name)

            if _get_extension(path=remote_path) in exclude_extensions:
                continue

            if remote_path not in self._skip_set or not use_skipables:
                local_path = os.path.join(local_dir, name.strip('/'))

                if name.endswith('/'):
                    self.pull_continue(remote_path, local_path, use_skipables, exclude_extensions)
                    continue

                self.download_file(remote_path, local_path, exclude_extensions)

