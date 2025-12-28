import hashlib
import logging
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any

log = logging.getLogger(__name__)


class ComparisonStrategy(Enum):
    """Vergleichsstrategien für Dateivergleiche"""
    FAST = "fast"  # Pfad+Name + Größe + mtime
    SAFE = "safe"  # Zusätzlich Content-Hash
    HYBRID = "hybrid"  # Erst Heuristik, Hash nur bei Verdacht


class FileComparisonResult:
    """Ergebnis eines Dateivergleichs"""

    def __init__(
            self,
            files_identical: bool,
            size_different: bool = False,
            mtime_different: bool = False,
            hash_different: bool = False,
            mtime_diff_seconds: Optional[float] = None,
            local_newer: Optional[bool] = None,
            suspicion_reason: Optional[str] = None
    ):
        self.files_identical = files_identical
        self.size_different = size_different
        self.mtime_different = mtime_different
        self.hash_different = hash_different
        self.mtime_diff_seconds = mtime_diff_seconds
        self.local_newer = local_newer
        self.suspicion_reason = suspicion_reason


class FileComparator:
    """Klasse für Dateivergleiche mit verschiedenen Strategien"""

    def __init__(
            self,
            strategy: ComparisonStrategy = ComparisonStrategy.HYBRID,
            mtime_tolerance_seconds: int = 60
    ):
        self.strategy = strategy
        self.mtime_tolerance_seconds = mtime_tolerance_seconds

    def compare_files(
            self,
            local_path: str,
            remote_info: Dict[str, Any]
    ) -> FileComparisonResult:
        """
        Vergleicht eine lokale Datei mit Remote-Metadaten.

        Args:
            local_path: Pfad zur lokalen Datei
            remote_info: Dictionary mit Remote-Metadaten (von client.info())

        Returns:
            FileComparisonResult mit Vergleichsergebnissen
        """
        if not os.path.exists(local_path):
            # Lokale Datei existiert nicht
            return FileComparisonResult(files_identical=False)

        local_stat = os.stat(local_path)
        local_size = local_stat.st_size
        local_mtime = local_stat.st_mtime

        remote_size = int(remote_info.get('size', 0))
        remote_modified = remote_info.get('modified')

        # Parse Remote-mtime
        remote_mtime = None
        if remote_modified:
            try:
                # Format: 'Tue, 03 Jun 2025 08:29:42 +0000'
                remote_mtime = datetime.strptime(
                    remote_modified,
                    '%a, %d %b %Y %H:%M:%S %z'
                ).timestamp()
            except (ValueError, AttributeError) as e:
                log.warning(f"Konnte Remote-mtime nicht parsen: {remote_modified} - {e}")

        # Schneller Vergleich: Größe und mtime
        size_match = local_size == remote_size
        mtime_match = False
        mtime_diff_seconds = None
        local_newer = None

        if remote_mtime is not None:
            mtime_diff_seconds = abs(local_mtime - remote_mtime)
            within_tolerance = mtime_diff_seconds <= self.mtime_tolerance_seconds
            mtime_match = within_tolerance
            local_newer = local_mtime > remote_mtime

        # Heuristik: Wenn Größe und mtime übereinstimmen, sind Dateien wahrscheinlich identisch
        heuristic_match = size_match and (mtime_match if remote_mtime else size_match)

        if self.strategy == ComparisonStrategy.FAST:
            # Nur Heuristik verwenden
            return FileComparisonResult(
                files_identical=heuristic_match,
                size_different=not size_match,
                mtime_different=not mtime_match if remote_mtime else None,
                mtime_diff_seconds=mtime_diff_seconds,
                local_newer=local_newer
            )

        elif self.strategy == ComparisonStrategy.SAFE:
            # Immer Hash berechnen
            local_hash = self._calculate_file_hash(local_path)
            remote_hash = None  # Müssen wir downloaden, um Hash zu berechnen

            # Für SAFE-Strategie: Hash-Vergleich ist erforderlich
            # Da wir den Remote-Hash nicht haben, müssen wir die Datei herunterladen
            # Das wird in der downloader.py gehandhabt
            return FileComparisonResult(
                files_identical=heuristic_match,
                size_different=not size_match,
                mtime_different=not mtime_match if remote_mtime else None,
                mtime_diff_seconds=mtime_diff_seconds,
                local_newer=local_newer,
                suspicion_reason="Hash-Vergleich erforderlich (SAFE-Strategie)" if not heuristic_match else None
            )

        elif self.strategy == ComparisonStrategy.HYBRID:
            # Erst Heuristik, Hash nur bei Verdacht
            if heuristic_match:
                # Heuristik sagt: Dateien sind identisch
                return FileComparisonResult(
                    files_identical=True,
                    size_different=False,
                    mtime_different=False,
                    mtime_diff_seconds=mtime_diff_seconds,
                    local_newer=local_newer
                )
            else:
                # Verdacht: Dateien könnten unterschiedlich sein
                suspicion_reasons = []
                if not size_match:
                    suspicion_reasons.append("unterschiedliche Größe")
                if remote_mtime and not mtime_match:
                    suspicion_reasons.append("unterschiedliche mtime")

                return FileComparisonResult(
                    files_identical=False,
                    size_different=not size_match,
                    mtime_different=not mtime_match if remote_mtime else None,
                    mtime_diff_seconds=mtime_diff_seconds,
                    local_newer=local_newer,
                    suspicion_reason="; ".join(suspicion_reasons) if suspicion_reasons else "Verdacht auf Unterschied"
                )

        return FileComparisonResult(files_identical=False)

    def compare_with_hash(
            self,
            local_path: str,
            remote_path: str,
            remote_info: Dict[str, Any],
            remote_content_stream
    ) -> FileComparisonResult:
        """
        Vergleicht Dateien mit Hash-Vergleich (für SAFE-Strategie oder bei Verdacht in HYBRID).

        Args:
            local_path: Pfad zur lokalen Datei
            remote_path: Pfad zur Remote-Datei (für Logging)
            remote_info: Dictionary mit Remote-Metadaten
            remote_content_stream: Stream mit Remote-Dateiinhalt (z.B. von client.download_from)

        Returns:
            FileComparisonResult mit Hash-Vergleich
        """
        local_hash = self._calculate_file_hash(local_path)
        remote_hash = self._calculate_stream_hash(remote_content_stream)

        hash_match = local_hash == remote_hash

        # Zusätzliche Metadaten-Vergleiche
        local_stat = os.stat(local_path)
        local_size = local_stat.st_size
        local_mtime = local_stat.st_mtime

        remote_size = int(remote_info.get('size', 0))
        remote_modified = remote_info.get('modified')

        remote_mtime = None
        if remote_modified:
            try:
                remote_mtime = datetime.strptime(
                    remote_modified,
                    '%a, %d %b %Y %H:%M:%S %z'
                ).timestamp()
            except (ValueError, AttributeError):
                pass

        mtime_diff_seconds = None
        local_newer = None
        if remote_mtime is not None:
            mtime_diff_seconds = abs(local_mtime - remote_mtime)
            local_newer = local_mtime > remote_mtime

        return FileComparisonResult(
            files_identical=hash_match,
            size_different=local_size != remote_size,
            mtime_different=not (
                        abs(local_mtime - remote_mtime) <= self.mtime_tolerance_seconds) if remote_mtime else None,
            hash_different=not hash_match,
            mtime_diff_seconds=mtime_diff_seconds,
            local_newer=local_newer
        )

    def _calculate_file_hash(self, file_path: str) -> str:
        """Berechnet SHA-256 Hash einer Datei"""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except (IOError, OSError) as e:
            log.error(f"Fehler beim Berechnen des Hashs für {file_path}: {e}")
            return ""

    def _calculate_stream_hash(self, content_stream) -> str:
        """Berechnet SHA-256 Hash eines Streams (BytesIO oder iterierbar)"""
        sha256_hash = hashlib.sha256()
        try:
            # Wenn es ein BytesIO ist, lese direkt
            if hasattr(content_stream, 'read'):
                content_stream.seek(0)  # Zurücksetzen falls nötig
                while True:
                    chunk = content_stream.read(4096)
                    if not chunk:
                        break
                    sha256_hash.update(chunk)
            else:
                # Iterierbarer Stream
                for chunk in content_stream:
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except Exception as e:
            log.error(f"Fehler beim Berechnen des Stream-Hashs: {e}")
            return ""

