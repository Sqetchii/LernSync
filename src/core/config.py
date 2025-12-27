import configparser
import json
from pathlib import Path
from typing import Optional


class Config:
    def __init__(self, config_path: str = 'config.ini'):
        self._config = configparser.ConfigParser()
        self._config.read(config_path, encoding='utf-8')
    
    @property
    def webdav_host_name(self) -> str:
        return self._config['webdav']['host_name']
    
    @property
    def webdav_remote_path(self) -> str:
        return self._config['webdav']['remote_path']
    
    @property
    def webdav_local_path(self) -> str:
        return self._config['webdav']['local_path']
    
    @property
    def service(self) -> str:
        return self._config['webdav']['service']
    
    @property
    def use_skipables(self) -> bool:
        return self._config['webdav'].getboolean('use_skipables')
    
    @property
    def exclude_extensions(self) -> list[str]:
        return json.loads(self._config["webdav"]["exclude_extensions"])
    
    @property
    def poll_interval_seconds(self) -> int:
        if self._config.has_section("lernsax") and self._config.has_option("lernsax", "poll_interval_seconds"):
            return self._config.getint("lernsax", "poll_interval_seconds")
        return 30

