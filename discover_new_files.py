from __future__ import annotations

import configparser
import datetime
from dataclasses import dataclass, field
from typing import List, Union, Optional
from urllib.parse import unquote, urlsplit, parse_qs
import html as ihtml
import re
import requests
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
            folder = fm.group("folder").strip()  # z.B. "/Lernfeld 6/.../Test"

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


# === HTTP / JSON-RPC Client ===

JSONRPC_URL = "https://www.lernsax.de/jsonrpc.php"
PINNWAND_URL = "https://www.lernsax.de/wws/55.php"


def _find_batch_result_item(batch_response: list, method_name: str) -> Optional[dict]:
    """
    Sucht im JSON-RPC-Batch die Zeile, deren result.method == method_name ist.
    (So wie in deinen Postman-Snippets.)
    """
    for item in batch_response:
        if not isinstance(item, dict):
            continue
        result = item.get("result")
        if isinstance(result, dict) and result.get("method") == method_name:
            return item
    return None


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

    r = session.post(JSONRPC_URL, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    data = r.json()

    if not isinstance(data, list):
        raise RuntimeError("Response ist kein Array (kein JSON-RPC Batch?)")

    info_item = _find_batch_result_item(data, "get_information")
    if not info_item:
        raise RuntimeError("Kein get_information-Item gefunden")

    session_id = info_item.get("result", {}).get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise RuntimeError("Kein get_information.result.session_id in der Response gefunden")

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

    r = session.post(JSONRPC_URL, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    data = r.json()

    if not isinstance(data, list):
        raise RuntimeError("Response ist kein Array (kein JSON-RPC Batch?)")

    autologin_item = _find_batch_result_item(data, "get_url_for_autologin")
    if not autologin_item:
        raise RuntimeError("Kein get_url_for_autologin Entry gefunden")

    url = autologin_item.get("result", {}).get("url")
    if not isinstance(url, str) or "?" not in url:
        raise RuntimeError("get_url_for_autologin.result.url fehlt oder ist ungültig")

    qs = parse_qs(urlsplit(url).query)
    autologin_nonce = (qs.get("autologin_nonce") or [None])[0]
    if not isinstance(autologin_nonce, str) or not autologin_nonce:
        raise RuntimeError("Kein autologin_nonce in URL gefunden")

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
    return r.content


def main() -> None:
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')

    service = config['webdav']['service']
    username, password = get_credentials(service)

    with requests.Session() as s:
        session_id = request_1_login_and_get_session_id(s, username, password)
        autologin_nonce = request_2_set_session_and_get_autologin_nonce(s, session_id)

        # print("autologin_nonce:", autologin_nonce)

        raw_html = request_3_get_pinnwand_html(s, session_id)

        p = Pinnwand()
        neu = p.collect_new_files(raw_html)

        for f in neu:
            print(f.name, f.path, f.upload_date)


if __name__ == "__main__":
    main()
