import getpass
import keyring


class CredentialService:
    def __init__(self, service: str):
        self._service = service
    
    def get_credentials(self) -> tuple[str, str]:
        username = keyring.get_password(self._service, 'username')
        if username is not None:
            password = keyring.get_password(self._service, username)
            if password is not None:
                return username, password

        username = input('Username: ')
        password = getpass.getpass('Password: ')

        keyring.set_password(self._service, 'username', username)
        keyring.set_password(self._service, username, password)

        return username, password
    
    def delete_entry(self, username: str) -> None:
        try:
            keyring.delete_password(self._service, username)
        except Exception:
            pass

