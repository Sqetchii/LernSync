# LernSax WebDAV Synchronisationstool

Ein professionelles Python-Tool zur automatischen Synchronisation von Dateien zwischen LernSax und dem lokalen Dateisystem über WebDAV. Das Tool überwacht die LernSax-Pinnwand auf neue Dateien und lädt diese automatisch herunter, während es intelligente Konfliktbehandlung und verschiedene Vergleichsstrategien bietet.

## Inhaltsverzeichnis

- [Überblick](#überblick)
- [Funktionen](#funktionen)
- [Voraussetzungen](#voraussetzungen)
- [Installation](#installation)
- [Konfiguration](#konfiguration)
- [Verwendung](#verwendung)
- [Architektur](#architektur)
- [Konfliktbehandlung](#konfliktbehandlung)
- [Vergleichsstrategien](#vergleichsstrategien)
- [Troubleshooting](#troubleshooting)

## Überblick

Dieses Tool ermöglicht es, Dateien von LernSax automatisch auf den lokalen Computer zu synchronisieren. Es bietet zwei Betriebsmodi:

- **Listener-Modus**: Überwacht kontinuierlich die LernSax-Pinnwand auf neue Dateien und lädt diese automatisch herunter
- **Full-Sync-Modus**: Führt eine vollständige Synchronisation aller Dateien durch

Das Tool integriert sich nahtlos in LernSax, nutzt WebDAV für den Dateitransfer und bietet erweiterte Funktionen wie intelligente Konfliktbehandlung, Dateivergleiche und sichere Credential-Verwaltung.

## Funktionen

- ✅ **Automatische Dateiüberwachung**: Kontinuierliche Überwachung der LernSax-Pinnwand auf neue Dateien
- ✅ **Intelligente Konfliktbehandlung**: Mehrere Strategien zur Behandlung von Dateikonflikten
- ✅ **Flexible Vergleichsstrategien**: Drei Modi für Dateivergleiche (fast, safe, hybrid)
- ✅ **Sichere Credential-Verwaltung**: Integration mit dem System-Keyring für sichere Passwort-Speicherung
- ✅ **Session-Management**: Automatische Verwaltung von LernSax-Sessions
- ✅ **mtime-Synchronisation**: Erhaltung der Original-Zeitstempel von Remote-Dateien
- ✅ **Skipables-Liste**: Möglichkeit, bestimmte Dateien dauerhaft zu überspringen
- ✅ **Dateityp-Filterung**: Ausschluss bestimmter Dateitypen (z.B. große Video-Dateien)
- ✅ **Farbiges Logging**: Übersichtliche, farbige Konsolenausgabe für bessere Lesbarkeit

## Voraussetzungen

- Python 3.8 oder höher
- Zugang zu einem LernSax-Account mit WebDAV-Zugriff
- Internetverbindung

## Installation

1. **Repository klonen oder herunterladen**

2. **Abhängigkeiten installieren**

   ```bash
   pip install -r requirements.txt
   ```

   Die wichtigsten Abhängigkeiten:
   - `keyring`: Sichere Credential-Speicherung
   - `webdav3`: WebDAV-Client (lokal im `libs/` Verzeichnis)
   - `lxml`: XML-Verarbeitung
   - `requests`: HTTP-Requests
   - `colorlog`: Farbiges Logging

3. **Konfigurationsdatei anpassen**

   Siehe Abschnitt [Konfiguration](#konfiguration) für Details.

## Konfiguration

Die Konfiguration erfolgt über die Datei `config.ini`. Eine Beispielkonfiguration ist bereits vorhanden:

```ini
[webdav]
host_name = https://www.lernsax.de/webdav.php
remote_path = raum@deineschule.lernsax.de/storage/
local_path = tmp/
service = lernsax-webdav
use_skipables = True
exclude_extensions = [".avi"]

# Vergleichsstrategie: fast (Pfad+Name+Größe+mtime), safe (mit Hash), hybrid (Hash nur bei Verdacht)
comparison_strategy = fast

# Konfliktregel: overwrite (Remote gewinnt), skip (Lokal behalten), keep_both (beide mit Suffix), quarantine (in quarantine_path Ordner)
conflict_resolution = skip

# Backup vor Überschreiben (nur bei conflict_resolution=overwrite)
backup_before_overwrite = True

# Quarantäne-Ordner für Konflikte (nur bei conflict_resolution=quarantine)
quarantine_path = conflicts

# mtime-Toleranzfenster in Sekunden (±Wert, z.B. 60 = ±1 Minute)
mtime_tolerance_seconds = 60

[lernsax]
poll_interval_seconds = 10
```

### Konfigurationsoptionen

#### `[webdav]` Sektion

- **`host_name`**: Die WebDAV-URL Ihres LernSax-Servers
- **`remote_path`**: Der Remote-Pfad auf dem Server (z.B. `it242@bszetdd.lernsax.de/storage/`)
- **`local_path`**: Der lokale Pfad, in den Dateien heruntergeladen werden sollen
- **`service`**: Service-Name für die Keyring-Integration
- **`use_skipables`**: Aktiviert/deaktiviert die Verwendung der `skipables.txt` Datei
- **`exclude_extensions`**: Liste von Dateiendungen, die ausgeschlossen werden sollen (JSON-Format)
- **`comparison_strategy`**: Vergleichsstrategie (`fast`, `safe`, `hybrid`) - siehe [Vergleichsstrategien](#vergleichsstrategien)
- **`conflict_resolution`**: Konfliktbehandlungsstrategie (`overwrite`, `skip`, `keep_both`, `quarantine`) - siehe [Konfliktbehandlung](#konfliktbehandlung)
- **`backup_before_overwrite`**: Erstellt ein Backup vor dem Überschreiben (nur bei `overwrite`)
- **`quarantine_path`**: Pfad für den Quarantäne-Ordner (nur bei `quarantine`)
- **`mtime_tolerance_seconds`**: Toleranzfenster für mtime-Vergleiche in Sekunden

#### `[lernsax]` Sektion

- **`poll_interval_seconds`**: Intervall in Sekunden, in dem die Pinnwand auf neue Dateien geprüft wird (nur Listener-Modus)

## Verwendung

### Grundlegende Verwendung

**Listener-Modus** (Standard):
```bash
python main.py
```

**Full-Sync-Modus**:
```bash
python main.py --mode full-sync
```

### Erweiterte Optionen

```bash
python main.py [OPTIONEN]
```

**Verfügbare Optionen:**

- `--mode {listener,full-sync}`: Betriebsmodus (Standard: `listener`)
- `--config PATH`: Pfad zur Konfigurationsdatei (Standard: `config.ini`)
- `--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}`: Logging-Level (Standard: `INFO`)

**Beispiele:**

```bash
# Listener-Modus mit Debug-Logging
python main.py --mode listener --log-level DEBUG

# Full-Sync mit benutzerdefinierter Konfiguration
python main.py --mode full-sync --config my_config.ini

# Nur Logging-Level ändern
python main.py --log-level WARNING
```

### Erste Anmeldung

Beim ersten Start werden Sie zur Eingabe Ihrer LernSax-Credentials aufgefordert:
- **Benutzername**: Ihr LernSax-Benutzername
- **Passwort**: Ihr LernSax-Passwort

Die Credentials werden sicher im System-Keyring gespeichert und müssen bei zukünftigen Starts nicht erneut eingegeben werden.

## Architektur

Das Projekt ist modular aufgebaut:

```
pzm/
├── main.py                 # Entry-Point mit CLI-Argumenten
├── config.ini              # Konfigurationsdatei
├── requirements.txt        # Python-Abhängigkeiten
├── skipables.txt          # Liste von Dateien, die übersprungen werden sollen
│
├── src/
│   ├── core/              # Kern-Funktionalität
│   │   ├── config.py      # Konfigurationsverwaltung
│   │   └── credentials.py # Credential-Service
│   │
│   ├── lernsax/           # LernSax-spezifische Funktionalität
│   │   ├── session.py     # Session-Management für LernSax
│   │   ├── pinnwand.py    # Pinnwand-Parser
│   │   └── listener.py    # Listener für neue Dateien
│   │
│   ├── webdav/            # WebDAV-Funktionalität
│   │   ├── client.py      # WebDAV-Client-Wrapper
│   │   ├── downloader.py  # Download-Logik
│   │   ├── file_comparator.py  # Dateivergleichs-Strategien
│   │   └── conflict_handler.py # Konfliktbehandlung
│   │
│   ├── services/          # Service-Layer
│   │   └── sync_service.py # Haupt-Synchronisationsservice
│   │
│   ├── models/            # Datenmodelle
│   │   └── datei.py       # Datei-Modell
│   │
│   └── utils/             # Utilities
│       └── keyring.py     # Keyring-Hilfsfunktionen
│
└── libs/                   # Lokale Bibliotheken
    └── webdav-client-python-3/  # WebDAV-Client-Bibliothek
```

### Datenfluss

1. **Listener-Modus**:
   - `LernSaxListener` überwacht die Pinnwand in konfigurierten Intervallen
   - Neue Dateien werden erkannt und an `SyncService` übergeben
   - `WebDavDownloader` lädt die Dateien herunter
   - `FileComparator` vergleicht lokale und Remote-Dateien
   - `ConflictHandler` behandelt Konflikte entsprechend der Konfiguration

2. **Full-Sync-Modus**:
   - `SyncService` initialisiert den WebDAV-Client
   - `WebDavDownloader.pull_continue()` synchronisiert rekursiv alle Dateien
   - Gleiche Vergleichs- und Konfliktbehandlungslogik wie im Listener-Modus

## Konfliktbehandlung

Das Tool bietet vier Strategien zur Behandlung von Dateikonflikten:

### 1. `overwrite` (Standard)
Die Remote-Datei überschreibt die lokale Datei. Optional kann ein Backup erstellt werden (`backup_before_overwrite = True`).

**Verwendung:** Wenn Sie immer die neueste Version vom Server haben möchten.

### 2. `skip`
Die lokale Datei wird beibehalten, die Remote-Änderung wird übersprungen.

**Verwendung:** Wenn lokale Änderungen Priorität haben sollen.

### 3. `keep_both`
Beide Versionen werden behalten. Die lokale Datei wird mit einem Timestamp-Suffix umbenannt.

**Verwendung:** Wenn Sie beide Versionen behalten möchten.

### 4. `quarantine`
Beide Versionen werden in einen separaten Quarantäne-Ordner verschoben, wobei die Ordnerstruktur erhalten bleibt.

**Verwendung:** Wenn Sie Konflikte manuell prüfen möchten, bevor Sie sie lösen.

## Vergleichsstrategien

Das Tool bietet drei Strategien zum Vergleich von Dateien:

### 1. `fast` (Schnell)
Vergleicht nur Metadaten:
- Dateiname und Pfad
- Dateigröße
- mtime (Modifikationszeit) innerhalb des Toleranzfensters

**Vorteile:** Sehr schnell, keine Downloads erforderlich  
**Nachteile:** Kann bei identischen Metadaten aber unterschiedlichem Inhalt fehlschlagen

### 2. `safe` (Sicher)
Führt zusätzlich einen Hash-Vergleich durch:
- Alle Prüfungen von `fast`
- SHA-256 Hash-Vergleich des Dateiinhalts

**Vorteile:** 100% sicher, erkennt alle Unterschiede  
**Nachteile:** Langsamer, erfordert Download für Hash-Berechnung

### 3. `hybrid` (Empfohlen)
Kombiniert beide Ansätze:
- Verwendet zunächst die schnelle Heuristik
- Führt Hash-Vergleich nur bei Verdacht durch (unterschiedliche Größe oder mtime)

**Vorteile:** Guter Kompromiss zwischen Geschwindigkeit und Sicherheit  
**Nachteile:** Kann bei sehr seltenen Edge-Cases fehlschlagen

## Troubleshooting

### Problem: "Fehlercode: 401, Benutzername oder Passwort sind falsch"

**Lösung:**
1. Überprüfen Sie Ihre Credentials in der Konfiguration
2. Das Tool löscht automatisch gespeicherte Credentials bei Fehlern
3. Geben Sie Ihre Credentials beim nächsten Start erneut ein

### Problem: "Keine Leserechte" für bestimmte Dateien

**Lösung:**
- Diese Dateien werden automatisch zur `skipables.txt` hinzugefügt
- Sie können die Datei manuell bearbeiten, um Einträge zu entfernen

### Problem: Session wird ungültig

**Lösung:**
- Das Tool erkennt automatisch ungültige Sessions und erstellt eine neue
- Keine manuelle Intervention erforderlich

### Problem: Dateien werden nicht heruntergeladen

**Mögliche Ursachen:**
1. Datei ist in `skipables.txt` eingetragen
2. Dateiendung ist in `exclude_extensions` aufgelistet
3. Datei existiert bereits lokal und `conflict_resolution = skip`
4. Logging-Level auf `DEBUG` setzen für detaillierte Informationen

### Problem: Keyring-Fehler

**Lösung:**
- Stellen Sie sicher, dass ein Keyring-Backend installiert ist
- Windows: Windows Credential Manager wird automatisch verwendet
- Linux: Installieren Sie `python3-keyring` oder ein anderes Backend
- macOS: Keychain wird automatisch verwendet

## Weitere Informationen

### Skipables-Datei

Die Datei `skipables.txt` enthält eine Liste von Remote-Pfaden, die beim Download übersprungen werden sollen. Diese Datei wird automatisch erstellt, wenn `use_skipables = True` gesetzt ist. Dateien werden automatisch hinzugefügt, wenn:
- Keine Leserechte vorhanden sind (403-Fehler)
- Andere Fehler beim Download auftreten

Sie können die Datei manuell bearbeiten, um Einträge zu entfernen oder hinzuzufügen.

### Logging

Das Tool verwendet farbiges Logging für bessere Lesbarkeit:
- 🟢 **INFO**: Normale Operationen
- 🟡 **WARNING**: Warnungen (z.B. Dateien übersprungen)
- 🔴 **ERROR**: Fehler (z.B. Download fehlgeschlagen)
- 🔵 **DEBUG**: Detaillierte Debug-Informationen

### Performance-Tipps

1. **Vergleichsstrategie**: Verwenden Sie `fast` für große Dateienmengen, `hybrid` für einen guten Kompromiss
2. **Poll-Intervall**: Erhöhen Sie `poll_interval_seconds` für weniger Server-Last
3. **Exclude Extensions**: Fügen Sie große Dateitypen (z.B. `.avi`, `.mp4`) zu `exclude_extensions` hinzu
4. **Skipables**: Nutzen Sie die Skipables-Liste für Dateien, die nicht synchronisiert werden sollen

## Lizenz

Dieses Projekt ist für den persönlichen Gebrauch bestimmt.

## Support

Bei Problemen oder Fragen:
1. Überprüfen Sie die Logs mit `--log-level DEBUG`
2. Überprüfen Sie die Konfiguration in `config.ini`
3. Stellen Sie sicher, dass alle Abhängigkeiten installiert sind

---

**Hinweis:** Dieses Tool ist nicht offiziell mit LernSax verbunden und wird als Open-Source-Projekt bereitgestellt.
