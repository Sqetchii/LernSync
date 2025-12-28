import configparser
import json
from pathlib import Path
from typing import Optional


class Config:
    def __init__(self, config_path: str = 'config.ini'):
        self._config = configparser.ConfigParser()
        self._config.read(config_path, encoding='utf-8')

    @property
    def webdav_host_name(self) -> str:
        return self._config['webdav']['host_name']

    @property
    def webdav_remote_path(self) -> str:
        return self._config['webdav']['remote_path']

    @property
    def webdav_local_path(self) -> str:
        return self._config['webdav']['local_path']

    @property
    def service(self) -> str:
        return self._config['webdav']['service']

    @property
    def use_skipables(self) -> bool:
        return self._config['webdav'].getboolean('use_skipables')

    @property
    def exclude_extensions(self) -> list[str]:
        return json.loads(self._config["webdav"]["exclude_extensions"])

    @property
    def poll_interval_seconds(self) -> int:
        if self._config.has_section("lernsax") and self._config.has_option("lernsax", "poll_interval_seconds"):
            return self._config.getint("lernsax", "poll_interval_seconds")
        return 30

    @property
    def comparison_strategy(self) -> str:
        """Vergleichsstrategie: fast, safe, hybrid"""
        if self._config.has_option("webdav", "comparison_strategy"):
            return self._config["webdav"]["comparison_strategy"].lower()
        return "hybrid"

    @property
    def conflict_resolution(self) -> str:
        """Konfliktregel: overwrite, skip, keep_both, quarantine"""
        if self._config.has_option("webdav", "conflict_resolution"):
            return self._config["webdav"]["conflict_resolution"].lower()
        return "overwrite"

    @property
    def backup_before_overwrite(self) -> bool:
        """Backup vor Überschreiben erstellen"""
        if self._config.has_option("webdav", "backup_before_overwrite"):
            return self._config["webdav"].getboolean("backup_before_overwrite")
        return False

    @property
    def quarantine_path(self) -> str:
        """Pfad für Quarantäne-Ordner"""
        if self._config.has_option("webdav", "quarantine_path"):
            return self._config["webdav"]["quarantine_path"]
        return "conflicts"

    @property
    def mtime_tolerance_seconds(self) -> int:
        """mtime-Toleranzfenster in Sekunden"""
        if self._config.has_option("webdav", "mtime_tolerance_seconds"):
            return self._config.getint("webdav", "mtime_tolerance_seconds")
        return 60

