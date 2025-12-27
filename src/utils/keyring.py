import logging
import keyring
from keyring.errors import PasswordDeleteError, InitError, KeyringError

log = logging.getLogger(__name__)


class KeyringUtils:
    @staticmethod
    def delete_entry(service: str, username: str) -> None:
        try:
            keyring.delete_password(service, username)
            log.info('Keyring-Eintrag gelöscht: service=%s user=%s', service, username)
        except PasswordDeleteError as e:
            log.warning('Konnte Keyring-Eintrag nicht löschen (fehlend/gesperrt): %s', e)
        except InitError as e:
            log.error('Keyring konnte nicht initialisiert werden: %s', e)
        except KeyringError as e:
            log.error('Allgemeiner Keyring-Fehler: %s', e)

