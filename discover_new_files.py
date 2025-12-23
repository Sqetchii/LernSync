from __future__ import annotations

import configparser
import datetime
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Union, Optional, Any, Tuple, Set
from urllib.parse import unquote, urlsplit, parse_qs
import html as ihtml
import re

import requests
import keyring

from credential_service import get_credentials
from datei import Datei


@dataclass
class Pinnwand:
    dateien: List[Datei] = field(default_factory=list)

    def collect_new_files(self, html_source: Union[str, bytes]) -> List[Datei]:
        if isinstance(html_source, bytes):
            html_source = html_source.decode("iso-8859-1", errors="replace")

        entry_re = re.compile(r'<div\s+class="entry_inner"[^>]*>(.*?)</div>', re.I | re.S)
        date_re = re.compile(r"</i>\s*<i>\s*(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})\s*</i>", re.I | re.S)
        folder_re = re.compile(r'im\s+Ordner\s+"(?P<folder>[^"]+)"', re.I | re.S)
        link_re = re.compile(
            r'<a[^>]*class="braces_function_files"[^>]*onclick="return\s+open_document\(\'(?P<url>[^\']+)\'\);?"[^>]*>(?P<name>[^<]+)</a>',
            re.I | re.S,
        )

        def _get_raw_query_param(url: str, key: str) -> str:
            q = url.split("?", 1)[1] if "?" in url else ""
            m = re.search(r"(?:^|&)" + re.escape(key) + r"=([^&]*)", q)
            return m.group(1) if m else ""

        existing_keys = {(d.path, d.name, d.upload_date) for d in self.dateien}
        new_files: List[Datei] = []

        for entry_html in entry_re.findall(html_source):
            if "Dateiablage" not in entry_html:
                continue

            dm = date_re.search(entry_html)
            if not dm:
                continue
            upload_date = datetime.datetime.strptime(dm.group(1), "%d.%m.%Y %H:%M")

            entry_text = ihtml.unescape(entry_html)
            fm = folder_re.search(entry_text)
            if not fm:
                continue
            folder = fm.group("folder").strip()

            for m in link_re.finditer(entry_html):
                url = m.group("url")
                name = ihtml.unescape(m.group("name")).strip()

                open_group_raw = _get_raw_query_param(url, "open_group")
                if not open_group_raw:
                    continue

                path = f"{unquote(open_group_raw)}/storage/{folder.lstrip('/')}"
                key = (path, name, upload_date)
                if key in existing_keys:
                    continue

                d = Datei(name=name, path=path, upload_date=upload_date)
                self.dateien.append(d)
                new_files.append(d)
                existing_keys.add(key)

        return new_files


JSONRPC_URL = "https://www.lernsax.de/jsonrpc.php"
PINNWAND_URL = "https://www.lernsax.de/wws/55.php"

LOGIN_ERRNO_ACCESS_DENIED = 107
SESSION_ERRNO_NOT_VALID = 106


class LernSaxError(RuntimeError):
    pass


class AuthenticationError(LernSaxError):
    pass


class SessionInvalidError(LernSaxError):
    pass


@dataclass(slots=True)
class JsonRpcFatal:
    method: Optional[str]
    errno: Optional[int]
    error: Optional[str]


def _parse_fatals(batch: Any) -> List[JsonRpcFatal]:
    fatals: List[JsonRpcFatal] = []
    if not isinstance(batch, list):
        return fatals

    for item in batch:
        if not isinstance(item, dict):
            continue
        result = item.get("result")
        if not isinstance(result, dict):
            continue
        if str(result.get("return", "")).upper() != "FATAL":
            continue

        raw_errno = result.get("errno")
        try:
            errno = int(raw_errno)
        except (TypeError, ValueError):
            errno = None

        fatals.append(
            JsonRpcFatal(
                method=result.get("method"),
                errno=errno,
                error=result.get("error"),
            )
        )
    return fatals


def _find_result_by_method(batch: Any, method_name: str) -> Optional[dict]:
    if not isinstance(batch, list):
        return None
    for item in batch:
        if not isinstance(item, dict):
            continue
        result = item.get("result")
        if isinstance(result, dict) and result.get("method") == method_name:
            return result
    return None


def _raise_if_login_failed(batch: Any) -> None:
    for f in _parse_fatals(batch):
        if f.errno == LOGIN_ERRNO_ACCESS_DENIED or (f.error and "Access denied" in f.error):
            raise AuthenticationError(f"Login fehlgeschlagen: errno={f.errno}, error={f.error}")


def _raise_if_session_invalid(batch: Any) -> None:
    for f in _parse_fatals(batch):
        if f.errno == SESSION_ERRNO_NOT_VALID or (f.error and "Session key not valid" in f.error):
            raise SessionInvalidError(f"Session ungültig: errno={f.errno}, error={f.error}")


def _post_jsonrpc(session: requests.Session, headers: dict[str, str], body: list[dict[str, Any]]) -> list[
    dict[str, Any]]:
    r = session.post(JSONRPC_URL, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise LernSaxError("Response ist kein Array (kein JSON-RPC Batch?)")
    return data


def request_1_login_and_get_session_id(session: requests.Session, login: str, password: str) -> str:
    headers = {
        "User-Agent": "LernSax de.digionline.lernsax/4.2.0(408) iOS Version 26.1 (Build 23B85)(RN)",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }
    body = [
        {
            "jsonrpc": "2.0",
            "method": "login",
            "id": 1,
            "params": {"login": login, "password": password, "get_miniature": True},
        },
        {"jsonrpc": "2.0", "method": "set_focus", "id": 2, "params": {"object": "trusts"}},
        {
            "jsonrpc": "2.0",
            "method": "register_master",
            "id": 3,
            "params": {"remote_application": "wwa", "remote_title": "Android App", "remote_ident": "Guest"},
        },
        {"jsonrpc": "2.0", "method": "set_focus", "id": 4, "params": {"object": "settings"}},
        {"jsonrpc": "2.0", "method": "get_information", "id": 5, "params": {}},
    ]

    data = _post_jsonrpc(session, headers, body)
    _raise_if_login_failed(data)

    info = _find_result_by_method(data, "get_information")
    session_id = info.get("session_id") if isinstance(info, dict) else None
    if not isinstance(session_id, str) or not session_id:
        raise LernSaxError("Kein get_information.result.session_id in der Response gefunden")

    return session_id


def request_2_set_session_and_get_autologin_nonce(session: requests.Session, session_id: str) -> str:
    headers = {
        "Host": "www.lernsax.de",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Accept-Language": "de-DE,de;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "User-Agent": "LernSax de.digionline.lernsax/4.2.0(408) iOS Version 26.1 (Build 23B85)(RN)",
        "Priority": "u=3, i",
        "Connection": "keep-alive",
    }
    body = [
        {"jsonrpc": "2.0", "method": "set_session", "id": 1, "params": {"session_id": session_id}},
        {"jsonrpc": "2.0", "method": "set_focus", "id": 2, "params": {"object": "trusts"}},
        {
            "jsonrpc": "2.0",
            "method": "get_url_for_autologin",
            "id": 3,
            "params": {
                "secondary_session": True,
                "disable_reception_of_quick_messages": True,
                "disable_logout": True,
                "ping_master": True,
                "locale": "de",
                "target_url_path": "55.php",
            },
        },
        {"jsonrpc": "2.0", "method": "get_information", "id": 4, "params": {}},
    ]

    data = _post_jsonrpc(session, headers, body)
    _raise_if_session_invalid(data)

    autologin = _find_result_by_method(data, "get_url_for_autologin")
    url = autologin.get("url") if isinstance(autologin, dict) else None
    if not isinstance(url, str) or "?" not in url:
        raise LernSaxError("get_url_for_autologin.result.url fehlt oder ist ungültig")

    qs = parse_qs(urlsplit(url).query)
    autologin_nonce = (qs.get("autologin_nonce") or [None])[0]
    if not isinstance(autologin_nonce, str) or not autologin_nonce:
        raise LernSaxError("Kein autologin_nonce in URL gefunden")

    return autologin_nonce


def request_3_get_pinnwand_html(session: requests.Session, session_id: str) -> bytes:
    headers = {
        "Host": "www.lernsax.de",
        "Sec-Fetch-Dest": "iframe",
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.1 Mobile/15E148 Safari/604.1"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.lernsax.de/wws/9.php",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Accept-Language": "de-DE,de;q=0.9",
        "Priority": "u=0, i",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    r = session.get(PINNWAND_URL, headers=headers, params={"sid": session_id}, timeout=30)
    r.raise_for_status()

    content = r.content
    if isinstance(content, (bytes, bytearray, memoryview)):
        text = bytes(content).decode("iso-8859-1", errors="ignore")
    else:
        text = ""

    if "Session key not valid" in text:
        raise SessionInvalidError("Session ungültig (HTML): Session key not valid.")

    return r.content


def _keyring_service_for_lernsax_session(service: str) -> str:
    return f"{service}:lernsax"


def load_session_id_from_keyring(service: str, username: str) -> Optional[str]:
    sid = keyring.get_password(_keyring_service_for_lernsax_session(service), username)
    return sid if isinstance(sid, str) and sid else None


def save_session_id_to_keyring(service: str, username: str, session_id: str) -> None:
    keyring.set_password(_keyring_service_for_lernsax_session(service), username, session_id)


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


def fetch_pinnwand_files_once(
        session: requests.Session,
        service: str,
        username: str,
        password: str,
        session_id: Optional[str],
) -> tuple[Optional[str], Optional[str], List[Datei]]:
    if session_id:
        autologin_nonce = request_2_set_session_and_get_autologin_nonce(session, session_id)
        raw_html = request_3_get_pinnwand_html(session, session_id)
        p = Pinnwand()
        files = p.collect_new_files(raw_html)
        return session_id, autologin_nonce, files

    session_id = request_1_login_and_get_session_id(session, username, password)
    save_session_id_to_keyring(service, username, session_id)
    autologin_nonce = request_2_set_session_and_get_autologin_nonce(session, session_id)
    raw_html = request_3_get_pinnwand_html(session, session_id)
    p = Pinnwand()
    files = p.collect_new_files(raw_html)
    return session_id, autologin_nonce, files


def run_listener(poll_interval_seconds: int = 30) -> None:
    config = configparser.ConfigParser()
    config.read("config.ini", encoding="utf-8")

    service = config["webdav"]["service"]
    username, password = get_credentials(service)

    last_keys = load_last_file_keys()
    new_files: List[Datei] = []

    session_id = load_session_id_from_keyring(service, username)

    with requests.Session() as s:
        while True:
            try:
                session_id, autologin_nonce, files = fetch_pinnwand_files_once(s, service, username, password,
                                                                               session_id)
            except SessionInvalidError:
                session_id = None
                session_id, autologin_nonce, files = fetch_pinnwand_files_once(s, service, username, password,
                                                                               session_id)

            current_new: List[Datei] = []
            for f in files:
                k = _file_key(f)
                if k not in last_keys:
                    current_new.append(f)

            if current_new:
                for f in current_new:
                    print(f"NEW FILE: {f.name} | {f.path} | {f.upload_date.isoformat()}")
                new_files.extend(current_new)
                for f in current_new:
                    last_keys.add(_file_key(f))
                save_last_file_keys(last_keys)

            time.sleep(poll_interval_seconds)


def main() -> None:
    config = configparser.ConfigParser()
    config.read("config.ini", encoding="utf-8")

    poll_interval_seconds = 30
    if config.has_section("lernsax") and config.has_option("lernsax", "poll_interval_seconds"):
        poll_interval_seconds = config.getint("lernsax", "poll_interval_seconds")

    run_listener(poll_interval_seconds=poll_interval_seconds)

if __name__ == "__main__":
    main()
