import getpass
import keyring

SERVICE = "lernsax-webdav"

def get_credentials():
    username = keyring.get_password(SERVICE, "username")
    if username is not None:
        password = keyring.get_password(SERVICE, username)
        if password is not None:
            return username, password

    username = input("Username: ")
    password = getpass.getpass("Password: ")

    keyring.set_password(SERVICE, "username", username)
    keyring.set_password(SERVICE, username, password)

    return username, password