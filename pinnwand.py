from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Union
from urllib.parse import unquote
import html as ihtml
import datetime
import re

from datei import Datei


@dataclass
class Pinnwand:
    dateien: List[Datei] = field(default_factory=list)

    def collect_new_files(self, html_source: Union[str, bytes]) -> List[Datei]:
        """
        Liest alle Dateien aus Pinnwand-Nachrichten, die 'Dateiablage' enthalten,
        und hängt neue (noch nicht vorhandene) an self.dateien an.

        Returns: Liste der neu hinzugefügten Dateien.
        """
        if isinstance(html_source, bytes):
            html_source = html_source.decode("iso-8859-1", errors="replace")

        # grobe Segmentierung pro Nachricht
        entry_re = re.compile(r'<div\s+class="entry_inner"[^>]*>(.*?)</div>', re.I | re.S)

        # Upload-Datum (steht im HTML als zweites <i>...</i> in der Entry-Zeile)
        date_re = re.compile(
            r"</i>\s*<i>\s*(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})\s*</i>",
            re.I | re.S,
        )

        # Ordner-Pfad steht im Text: im Ordner "/Lernfeld .../Test"
        folder_re = re.compile(r'im\s+Ordner\s+"(?P<folder>[^"]+)"', re.I | re.S)

        # Dateilink: Name im a-Text, URL steckt im onclick open_document('...')
        link_re = re.compile(
            r'<a[^>]*class="braces_function_files"[^>]*onclick="return\s+open_document\(\'(?P<url>[^\']+)\'\);?"[^>]*>(?P<name>[^<]+)</a>',
            re.I | re.S,
        )

        def _get_raw_query_param(url: str, key: str) -> str:
            q = url.split("?", 1)[1] if "?" in url else ""
            m = re.search(r"(?:^|&)" + re.escape(key) + r"=([^&]*)", q)
            return m.group(1) if m else ""

        # Dedupe ohne Datei-ID: (path, name, upload_date)
        existing_keys = {(d.path, d.name, d.upload_date) for d in self.dateien}
        new_files: List[Datei] = []

        for entry_html in entry_re.findall(html_source):
            if "Dateiablage" not in entry_html:
                continue

            # Datum parsen
            dm = date_re.search(entry_html)
            if not dm:
                continue
            upload_date = datetime.datetime.strptime(dm.group(1), "%d.%m.%Y %H:%M")

            # Ordner aus dem (unescaped) Text extrahieren
            entry_text = ihtml.unescape(entry_html)
            fm = folder_re.search(entry_text)
            if not fm:
                continue
            folder = fm.group("folder").strip()  # z.B. "/Lernfeld 6/.../Test"

            for m in link_re.finditer(entry_html):
                url = m.group("url")
                name = ihtml.unescape(m.group("name")).strip()

                open_group_raw = _get_raw_query_param(url, "open_group")  # z.B. it242%40...
                if not open_group_raw:
                    continue

                # gewünschtes Format:
                # it242@bszetdd.lernsax.de/Lernfeld 6/01_IT-Service/.../Test
                path = f"{unquote(open_group_raw)}/storage/{folder.lstrip('/')}"

                key = (path, name, upload_date)
                if key in existing_keys:
                    continue

                d = Datei(name=name, path=path, upload_date=upload_date)
                self.dateien.append(d)
                new_files.append(d)
                existing_keys.add(key)

        return new_files
