import logging
import credential_service
from webdav3.client import Client
from credential_service import get_credentials
from functions import pull_continue

log = logging.getLogger(__name__)

host_name = 'https://www.lernsax.de/webdav.php'
username, password = get_credentials()

options = {
    'webdav_hostname': f'{host_name}',
    'webdav_login': f'{username}',
    'webdav_password': f'{password}'
}
client = Client(options)
client.webdav.disable_check = True
# root_content = client.list()
# it242_content = client.list(root[3])
# storage_content = client.list(root[3] + it242[1])
remote_path = 'it242@bszetdd.lernsax.de/storage/'
local_path = r'C:\Users\nicol\OneDrive - Landratsamt Sächsische Schweiz Abt. Schul- und Liegenschaftsmanagement (SLM)\Berufsschule'

pull_continue(client, remote_path, local_path)
