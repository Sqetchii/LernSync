import argparse
import logging
import sys

from src.core.config import Config
from src.services.sync_service import SyncService


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


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
    
    args = parser.parse_args()
    
    try:
        config = Config(args.config)
    except Exception as e:
        print(f"Fehler beim Laden der Konfiguration: {e}", file=sys.stderr)
        sys.exit(1)
    
    service = SyncService(config)
    
    try:
        if args.mode == 'listener':
            service.run_listener_mode()
        elif args.mode == 'full-sync':
            service.run_full_sync()
    except KeyboardInterrupt:
        print("\nBeendet durch Benutzer.")
        sys.exit(0)
    except Exception as e:
        print(f"Unerwarteter Fehler: {e}", file=sys.stderr)
        logging.exception("Unerwarteter Fehler")
        sys.exit(1)


if __name__ == '__main__':
    main()
