from __future__ import annotations

from typing import Optional, Any, List
from urllib.parse import urlsplit, parse_qs

import keyring
import requests

from src.lernsax.pinnwand import Pinnwand
from src.models.datei import Datei

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


class JsonRpcFatal:
    __slots__ = ('method', 'errno', 'error')
    
    def __init__(self, method: Optional[str], errno: Optional[int], error: Optional[str]):
        self.method = method
        self.errno = errno
        self.error = error


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


def _post_jsonrpc(session: requests.Session, headers: dict[str, str], body: list[dict[str, Any]]) -> list[dict[str, Any]]:
    r = session.post(JSONRPC_URL, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list):
        raise LernSaxError("Response ist kein Array (kein JSON-RPC Batch?)")
    return data


def _keyring_service_for_lernsax_session(service: str) -> str:
    return f"{service}:lernsax"


class LernSaxSession:
    def __init__(self, service: str):
        self._service = service
    
    def load_session_id(self, username: str) -> Optional[str]:
        sid = keyring.get_password(_keyring_service_for_lernsax_session(self._service), username)
        return sid if isinstance(sid, str) and sid else None
    
    def save_session_id(self, username: str, session_id: str) -> None:
        keyring.set_password(_keyring_service_for_lernsax_session(self._service), username, session_id)
    
    def login_and_get_session_id(self, session: requests.Session, login: str, password: str) -> str:
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
    
    def set_session_and_get_autologin_nonce(self, session: requests.Session, session_id: str) -> str:
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
    
    def get_pinnwand_html(self, session: requests.Session, session_id: str) -> bytes:
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
    
    def fetch_pinnwand_files_once(
        self,
        session: requests.Session,
        username: str,
        password: str,
        session_id: Optional[str],
    ) -> tuple[Optional[str], Optional[str], list[Datei]]:
        if session_id:
            autologin_nonce = self.set_session_and_get_autologin_nonce(session, session_id)
            raw_html = self.get_pinnwand_html(session, session_id)
            p = Pinnwand()
            files = p.collect_new_files(raw_html)
            return session_id, autologin_nonce, files

        session_id = self.login_and_get_session_id(session, username, password)
        self.save_session_id(username, session_id)
        autologin_nonce = self.set_session_and_get_autologin_nonce(session, session_id)
        raw_html = self.get_pinnwand_html(session, session_id)
        p = Pinnwand()
        files = p.collect_new_files(raw_html)
        return session_id, autologin_nonce, files

