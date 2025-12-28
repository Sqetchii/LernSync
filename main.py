import argparse
import logging
import sys

import colorlog

from src.core.config import Config
from src.services.sync_service import SyncService


def setup_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Handler für farbiges Logging auf der Konsole
    handler = colorlog.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    # Farbiges Format
    formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(levelname)-8s%(reset)s %(name)s: %(message)s',
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={},
        style='%'
    )

    handler.setFormatter(formatter)

    # Root Logger konfigurieren
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []  # Entferne vorhandene Handler
    root_logger.addHandler(handler)

    # Externe Logger auf WARNING setzen, um Spam zu vermeiden
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('webdav3').setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(
        description='WebDAV Sync Tool für LernSax',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--mode',
        choices=['listener', 'full-sync'],
        default='listener',
        help='Betriebsmodus: listener (automatischer Download neuer Dateien) oder full-sync (vollständiger Sync)'
    )
    parser.add_argument(
        '--config',
        default='config.ini',
        help='Pfad zur Konfigurationsdatei (Standard: config.ini)'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging-Level (Standard: INFO)'
    )

    args = parser.parse_args()

    # Logging initialisieren
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    try:
        config = Config(args.config)
        logger.info("Konfiguration erfolgreich geladen")
    except Exception as e:
        logger.critical(f"Fehler beim Laden der Konfiguration: {e}", exc_info=True)
        sys.exit(1)

    service = SyncService(config)

    try:
        if args.mode == 'listener':
            logger.info("Starte Listener-Modus")
            service.run_listener_mode()
        elif args.mode == 'full-sync':
            logger.info("Starte Full-Sync-Modus")
            service.run_full_sync()
    except KeyboardInterrupt:
        logger.info("Beendet durch Benutzer (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unerwarteter Fehler: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
