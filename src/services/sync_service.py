import logging
import os
from pathlib import Path
from typing import Optional

from src.core.config import Config
from src.core.credentials import CredentialService
from src.lernsax.listener import LernSaxListener
from src.models.datei import Datei
from src.utils.keyring import KeyringUtils
from src.webdav.client import WebDavClient
from src.webdav.downloader import WebDavDownloader
from webdav3.exceptions import ResponseErrorCode

log = logging.getLogger(__name__)


class SyncService:
    def __init__(self, config: Config):
        self._config = config
        self._credential_service = CredentialService(config.service)
        self._keyring_utils = KeyringUtils()
        self._webdav_client: Optional[WebDavClient] = None
        self._downloader: Optional[WebDavDownloader] = None
    
    def _ensure_webdav_client(self) -> WebDavClient:
        if self._webdav_client is None:
            username, password = self._credential_service.get_credentials()
            self._webdav_client = WebDavClient(
                self._config.webdav_host_name,
                username,
                password
            )
            self._downloader = WebDavDownloader(self._webdav_client.client)
        return self._webdav_client
    
    def _download_file(self, datei: Datei) -> bool:
        if self._downloader is None:
            self._ensure_webdav_client()
        
        remote_path = f"{datei.path.rstrip('/')}/{datei.name}"
        
        base_remote = self._config.webdav_remote_path.rstrip('/')
        if datei.path.startswith(base_remote):
            relative_path = datei.path[len(base_remote):].lstrip('/')
        else:
            relative_path = datei.path.replace(base_remote, '').lstrip('/')
        
        local_dir = Path(self._config.webdav_local_path) / relative_path
        local_path = local_dir / datei.name
        
        return self._downloader.download_file(
            remote_path,
            str(local_path),
            self._config.exclude_extensions
        )
    
    def _on_new_files(self, new_files: list[Datei]) -> None:
        if not self._webdav_client:
            try:
                self._ensure_webdav_client()
            except ResponseErrorCode as e:
                if getattr(e, 'code', None) == 401:
                    log.error(f'Fehlercode: {e.code}, Benutzername oder Passwort sind falsch.')
                    username, _ = self._credential_service.get_credentials()
                    self._keyring_utils.delete_entry(self._config.service, username)
                else:
                    log.error(f'Fehlercode: {e.code}, Unbekanntes Problem bei der Anmeldung.')
                return
        
        for datei in new_files:
            try:
                success = self._download_file(datei)
                if success:
                    print(f"Downloaded: {datei.name}")
                else:
                    print(f"Failed to download: {datei.name}")
            except Exception as e:
                log.error(f"Fehler beim Download von {datei.name}: {e}")
    
    def run_listener_mode(self) -> None:
        if self._config.use_skipables:
            try:
                Path('skipables.txt').open('x', encoding='utf-8').close()
            except FileExistsError:
                pass
        
        listener = LernSaxListener(
            self._config,
            self._credential_service,
            self._on_new_files
        )
        
        print("Listening for new files...")
        listener.run()
    
    def run_full_sync(self) -> None:
        if self._config.use_skipables:
            try:
                Path('skipables.txt').open('x', encoding='utf-8').close()
            except FileExistsError:
                pass
        
        while True:
            try:
                username, password = self._credential_service.get_credentials()
                webdav_client = WebDavClient(
                    self._config.webdav_host_name,
                    username,
                    password
                )
                
                print('Erfolgreicher Login.')
                downloader = WebDavDownloader(webdav_client.client)
                downloader.pull_continue(
                    self._config.webdav_remote_path,
                    self._config.webdav_local_path,
                    self._config.use_skipables,
                    self._config.exclude_extensions
                )
                break
            except ResponseErrorCode as e:
                if getattr(e, 'code', None) == 401:
                    log.error(f'Fehlercode: {e.code}, Benutzername oder Passwort sind falsch.')
                else:
                    log.error(f'Fehlercode: {e.code}, Unbekanntes Problem bei der Anmeldung.')
                username, _ = self._credential_service.get_credentials()
                self._keyring_utils.delete_entry(self._config.service, username)

