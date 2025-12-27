import os
import logging
from pathlib import Path
from typing import Set
from webdav3.client import Client
from webdav3.exceptions import WebDavException, ResponseErrorCode

log = logging.getLogger(__name__)


class WebDavDownloader:
    def __init__(self, client: Client, skipables_file: str = 'skipables.txt'):
        self._client = client
        self._skipables_file = skipables_file
        self._skip_set = self._load_skipables()
    
    def _load_skipables(self) -> Set[str]:
        try:
            with open(self._skipables_file, 'r', encoding='utf-8') as f:
                return {line.strip() for line in f if line.strip()}
        except FileNotFoundError:
            return set()
    
    def _join_remote(self, base: str, child: str) -> str:
        return base.rstrip('/') + '/' + child.lstrip('/')
    
    def _get_extension(self, path: str) -> str:
        _, extension = os.path.splitext(path)
        return extension
    
    def download_file(self, remote_path: str, local_path: str, exclude_extensions: list[str]) -> bool:
        if self._get_extension(remote_path) in exclude_extensions:
            return False
        
        os.makedirs(os.path.dirname(local_path) if os.path.dirname(local_path) else '.', exist_ok=True)
        
        try:
            self._client.download_sync(remote_path=remote_path, local_path=local_path)
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

            remote_path = self._join_remote(remote_dir, name)

            if self._get_extension(path=remote_path) in exclude_extensions:
                continue

            if remote_path not in self._skip_set or not use_skipables:
                local_path = os.path.join(local_dir, name.strip('/'))

                if name.endswith('/'):
                    self.pull_continue(remote_path, local_path, use_skipables, exclude_extensions)
                    continue

                self.download_file(remote_path, local_path, exclude_extensions)

