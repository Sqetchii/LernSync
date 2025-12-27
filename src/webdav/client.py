from webdav3.client import Client
from typing import Optional


class WebDavClient:
    def __init__(self, host_name: str, username: str, password: str):
        options = {
            'webdav_hostname': host_name,
            'webdav_login': username,
            'webdav_password': password
        }
        self._client = Client(options)
        self._client.webdav.disable_check = True
    
    @property
    def client(self) -> Client:
        return self._client
    
    def download_sync(self, remote_path: str, local_path: str) -> None:
        self._client.download_sync(remote_path=remote_path, local_path=local_path)

