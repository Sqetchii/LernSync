import logging
import configparser
from pathlib import Path
from webdav3.client import Client
from webdav3.exceptions import ResponseErrorCode
from credential_service import get_credentials
from functions import pull_continue
from utilities.clear_keyring import delete_entry

log = logging.getLogger(__name__)

config = configparser.ConfigParser()
config.read('config.ini')

host_name = config['webdav']['host_name']
remote_path = config['webdav']['remote_path']
local_path = config['webdav']['local_path']
service = config['webdav']['service']
use_skipables = config['webdav'].getboolean('use_skipables')

def main():
    if use_skipables:
        try:
            Path('skipables.txt').open('x', encoding='utf-8').close()
        except FileExistsError:
            pass

    while True:
        username, password = get_credentials(service)

        options = {
            'webdav_hostname': f'{host_name}',
            'webdav_login': f'{username}',
            'webdav_password': f'{password}'
        }
        try:
            client = Client(options)
            client.webdav.disable_check = True

            print('Erfolgreicher Login.')
            pull_continue(client, remote_path, local_path, use_skipables)
            break
        except ResponseErrorCode as e:
            if getattr(e, 'code', None) == 401:
                log.error(f'Fehlercode: {e.code}, Benutzername oder Passwort sind falsch.')
            else:
                log.error(f'Fehlercode: {e.code}, Unbekanntes Problem bei der Anmeldung.')
            delete_entry(service, username)

if __name__ == '__main__':
    main()