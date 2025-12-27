import json
import time
from pathlib import Path
from typing import Set, Tuple, Callable, Optional
import requests

from src.core.config import Config
from src.core.credentials import CredentialService
from src.lernsax.session import LernSaxSession, SessionInvalidError
from src.models.datei import Datei


FileKey = Tuple[str, str, str]


def _file_key(datei: Datei) -> FileKey:
    return (datei.name, datei.path, datei.upload_date.isoformat())


def _last_files_path() -> Path:
    tmp_dir = Path("tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir / "last_files.jsonl"


def load_last_file_keys() -> Set[FileKey]:
    p = _last_files_path()
    if not p.exists():
        return set()

    keys: Set[FileKey] = set()
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            name = obj.get("name")
            path = obj.get("path")
            upload_date = obj.get("upload_date")
            if isinstance(name, str) and isinstance(path, str) and isinstance(upload_date, str):
                keys.add((name, path, upload_date))
    return keys


def save_last_file_keys(keys: Set[FileKey]) -> None:
    p = _last_files_path()
    tmp = p.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for name, path, upload_date in sorted(keys):
            f.write(json.dumps({"name": name, "path": path, "upload_date": upload_date}, ensure_ascii=False) + "\n")
    tmp.replace(p)


class LernSaxListener:
    def __init__(
        self,
        config: Config,
        credential_service: CredentialService,
        on_new_files: Callable[[list[Datei]], None]
    ):
        self._config = config
        self._credential_service = credential_service
        self._on_new_files = on_new_files
        self._session_manager = LernSaxSession(config.service)
        self._last_keys = load_last_file_keys()
    
    def run(self, poll_interval_seconds: Optional[int] = None) -> None:
        if poll_interval_seconds is None:
            poll_interval_seconds = self._config.poll_interval_seconds
        
        username, password = self._credential_service.get_credentials()
        session_id = self._session_manager.load_session_id(username)

        with requests.Session() as session:
            while True:
                try:
                    session_id, _, files = self._session_manager.fetch_pinnwand_files_once(
                        session, username, password, session_id
                    )
                except SessionInvalidError:
                    session_id = None
                    session_id, _, files = self._session_manager.fetch_pinnwand_files_once(
                        session, username, password, session_id
                    )

                current_new: list[Datei] = []
                for f in files:
                    k = _file_key(f)
                    if k not in self._last_keys:
                        current_new.append(f)

                if current_new:
                    for f in current_new:
                        print(f"NEW FILE: {f.name} | {f.path} | {f.upload_date.isoformat()}")
                    self._on_new_files(current_new)
                    for f in current_new:
                        self._last_keys.add(_file_key(f))
                    save_last_file_keys(self._last_keys)

                time.sleep(poll_interval_seconds)

