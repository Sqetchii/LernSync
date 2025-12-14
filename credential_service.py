import getpass
import keyring


def get_credentials(service):
    username = keyring.get_password(service, 'username')
    if username is not None:
        password = keyring.get_password(service, username)
        if password is not None:
            return username, password

    username = input('Username: ')
    password = getpass.getpass('Password: ')

    keyring.set_password(service, 'username', username)
    keyring.set_password(service, username, password)

    return username, password
