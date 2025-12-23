import datetime
from dataclasses import dataclass


@dataclass(slots=True)
class Datei:
    name: str
    path: str
    upload_date: datetime.datetime