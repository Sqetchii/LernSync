import datetime
from dataclasses import dataclass


@dataclass(slots=True)
class Datei:
    name: str
    path: str
    upload_date: datetime.datetime

    def equals(self, other: object) -> bool:
        if not isinstance(other, Datei):
            return False
        return (self.name, self.path, self.upload_date) == (other.name, other.path, other.upload_date)