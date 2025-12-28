import logging
import os
import shutil
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class ConflictResolution(Enum):
    """Konfliktauflösungsstrategien"""
    OVERWRITE = "overwrite"  # Remote gewinnt
    SKIP = "skip"  # Lokal behalten
    KEEP_BOTH = "keep_both"  # Beide mit Suffix
    QUARANTINE = "quarantine"  # In Conflicts-Ordner


def _handle_skip(local_path: str, remote_path: str) -> bool:
    """Überspringt Remote-Änderung (Lokal behalten)"""
    log.info(f"Überspringe Remote-Änderung, behalte lokale Datei: {local_path} (Remote: {remote_path})")
    return False


def _create_backup_path(local_path: str) -> str:
    """Erstellt Backup-Pfad für lokale Datei"""
    path = Path(local_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.parent / f"{path.stem}_backup_{timestamp}{path.suffix}"
    return str(backup_path)


def _create_conflict_path(local_path: str) -> str:
    """Erstellt Konflikt-Pfad für lokale Datei"""
    path = Path(local_path)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    conflict_path = path.parent / f"{path.stem} (conflicted copy {timestamp}){path.suffix}"
    return str(conflict_path)


class ConflictHandler:
    """Klasse für die Behandlung von Dateikonflikten"""

    def __init__(
            self,
            resolution: ConflictResolution = ConflictResolution.OVERWRITE,
            backup_before_overwrite: bool = False,
            quarantine_path: str = "conflicts",
            local_base_path: Optional[str] = None
    ):
        self.resolution = resolution
        self.backup_before_overwrite = backup_before_overwrite
        self.quarantine_path = quarantine_path
        self.local_base_path = local_base_path

    def handle_conflict(
            self,
            local_path: str,
            remote_path: str,
            comparison_result
    ) -> bool:
        """
        Behandelt einen Dateikonflikt basierend auf der konfigurierten Strategie.

        Args:
            local_path: Pfad zur lokalen Datei
            remote_path: Remote-Pfad (für Logging)
            comparison_result: FileComparisonResult mit Vergleichsergebnissen

        Returns:
            True wenn die Datei heruntergeladen werden soll, False wenn übersprungen
        """
        if not os.path.exists(local_path):
            # Lokale Datei existiert nicht, kein Konflikt
            return True

        if self.resolution == ConflictResolution.OVERWRITE:
            return self._handle_overwrite(local_path, remote_path)

        elif self.resolution == ConflictResolution.SKIP:
            return _handle_skip(local_path, remote_path)

        elif self.resolution == ConflictResolution.KEEP_BOTH:
            return self._handle_keep_both(local_path, remote_path)

        elif self.resolution == ConflictResolution.QUARANTINE:
            return self._handle_quarantine(local_path, remote_path)

        # Default: überschreiben
        log.warning(f"Unbekannte Konfliktstrategie, verwende OVERWRITE für {remote_path}")
        return self._handle_overwrite(local_path, remote_path)

    def _handle_overwrite(self, local_path: str, remote_path: str) -> bool:
        """Überschreibt lokale Datei (Remote gewinnt)"""
        if self.backup_before_overwrite:
            backup_path = _create_backup_path(local_path)
            try:
                shutil.copy2(local_path, backup_path)
                log.info(f"Backup erstellt: {backup_path}")
            except (OSError, IOError) as e:
                log.warning(f"Konnte Backup nicht erstellen: {e}")

        log.info(f"Überschreibe lokale Datei: {local_path} (Remote: {remote_path})")
        return True

    def _handle_keep_both(self, local_path: str, remote_path: str) -> bool:
        """Behält beide Versionen, verschiebt lokale als Konfliktkopie"""
        try:
            conflict_path = _create_conflict_path(local_path)
            shutil.move(local_path, conflict_path)
            log.info(f"Lokale Datei als Konfliktkopie verschoben: {conflict_path} (Remote: {remote_path})")
            return True
        except (OSError, IOError) as e:
            log.error(f"Konnte lokale Datei nicht verschieben: {e}")
            # Fallback: überschreiben
            return self._handle_overwrite(local_path, remote_path)

    def _handle_quarantine(self, local_path: str, remote_path: str) -> bool:
        """Verschiebt beide Versionen in Quarantäne-Ordner"""
        try:
            # Extrahiere relativen Pfad aus local_path
            relative_path = self._extract_relative_path_from_local(local_path)
            relative_path_obj = Path(relative_path)
            
            # Erstelle Quarantäne-Ordner mit erhaltener Struktur
            quarantine_dir = Path(self.quarantine_path) / relative_path_obj.parent
            quarantine_dir.mkdir(parents=True, exist_ok=True)

            # Verschiebe lokale Datei in Quarantäne mit erhaltener Ordnerstruktur
            filename = relative_path_obj.name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_stem = Path(filename).stem
            file_suffix = Path(filename).suffix
            local_quarantine = quarantine_dir / f"{file_stem}_local_{timestamp}{file_suffix}"

            shutil.move(local_path, str(local_quarantine))
            log.info(f"Lokale Datei in Quarantäne verschoben: {local_quarantine} (Remote: {remote_path})")

            # Remote-Datei wird heruntergeladen, dann auch in Quarantäne verschieben
            # Das wird nach dem Download in downloader.py gehandhabt
            return True
        except (OSError, IOError) as e:
            log.error(f"Konnte Datei nicht in Quarantäne verschieben: {e}")
            # Fallback: überschreiben
            return self._handle_overwrite(local_path, remote_path)

    def _extract_relative_path_from_local(self, local_path: str) -> str:
        """
        Extrahiert den relativen Pfad aus dem local_path basierend auf local_base_path.
        
        Beispiel:
        - local_base_path: "tmp/Lernfeldübergreifend"
        - local_path: "tmp/Lernfeldübergreifend/datei.pdf"
        - Output: "Lernfeldübergreifend/datei.pdf"
        
        Falls local_base_path nicht gesetzt ist, wird versucht, das erste Verzeichnis zu entfernen.
        """
        local_path_obj = Path(local_path)
        
        if self.local_base_path:
            base_path_obj = Path(self.local_base_path)
            local_path_resolved = local_path_obj.resolve()
            base_path_resolved = base_path_obj.resolve()
            
            try:
                # Berechne den relativen Pfad vom local_base_path zum local_path
                relative_to_base = local_path_resolved.relative_to(base_path_resolved)
                
                # Extrahiere den relativen Teil von local_base_path (ohne erstes Verzeichnis)
                base_parts = base_path_obj.parts
                if len(base_parts) > 1:
                    # Nimm alle Teile außer dem ersten (z.B. "tmp/Lernfeldübergreifend" -> "Lernfeldübergreifend")
                    base_relative = '/'.join(base_parts[1:])
                    relative_str = str(relative_to_base).replace('\\', '/')
                    
                    if relative_str == '.':
                        # Falls relative_to_base nur '.' ist, nimm nur den base_relative
                        return base_relative
                    else:
                        # Kombiniere: base_relative + relative_to_base
                        return f"{base_relative}/{relative_str}"
                else:
                    # local_base_path hat nur ein Verzeichnis, verwende nur relative_to_base
                    return str(relative_to_base).replace('\\', '/')
            except ValueError:
                # Falls local_path nicht unter base_path liegt, versuche String-Matching
                base_str = str(base_path_resolved)
                local_str = str(local_path_resolved)
                if local_str.startswith(base_str):
                    relative = local_str[len(base_str):].lstrip('/\\')
                    # Füge den relativen Teil von base_path hinzu
                    base_parts = base_path_obj.parts
                    if len(base_parts) > 1:
                        base_relative = '/'.join(base_parts[1:])
                        if relative:
                            return f"{base_relative}/{relative}".replace('\\', '/')
                        else:
                            return base_relative
                    return relative.replace('\\', '/')
        
        # Fallback: Entferne das erste Verzeichnis
        parts = local_path_obj.parts
        if len(parts) > 1:
            return '/'.join(parts[1:])
        
        # Letzter Fallback: nur Dateiname
        return local_path_obj.name

    def move_to_quarantine_after_download(self, local_path: str, remote_path: str) -> Optional[str]:
        """
        Verschiebt heruntergeladene Datei in Quarantäne (für QUARANTINE-Strategie).

        Returns:
            Pfad zur Quarantäne-Datei oder None bei Fehler
        """
        if self.resolution != ConflictResolution.QUARANTINE:
            return None

        try:
            # Extrahiere relativen Pfad aus local_path
            relative_path = self._extract_relative_path_from_local(local_path)
            relative_path_obj = Path(relative_path)
            
            # Erstelle Quarantäne-Ordner mit erhaltener Struktur
            quarantine_dir = Path(self.quarantine_path) / relative_path_obj.parent
            quarantine_dir.mkdir(parents=True, exist_ok=True)

            # Erstelle Quarantäne-Dateiname mit Timestamp
            filename = relative_path_obj.name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_stem = Path(filename).stem
            file_suffix = Path(filename).suffix
            quarantine_file = quarantine_dir / f"{file_stem}_remote_{timestamp}{file_suffix}"

            if os.path.exists(local_path):
                shutil.move(local_path, str(quarantine_file))
                log.info(f"Remote-Datei in Quarantäne verschoben: {quarantine_file} (Remote: {remote_path})")
                return str(quarantine_file)
        except (OSError, IOError) as e:
            log.error(f"Konnte Remote-Datei nicht in Quarantäne verschieben: {e}")

        return None

