from mongodb_odm.models import Document
from pymongo import ASCENDING, IndexModel


class Ship(Document):
    name: str

    class ODMConfig(Document.ODMConfig):
        allow_inheritance = True
        collection_name = "ship_multilevel_collection"
        indexes = [IndexModel([("name", ASCENDING)], name="idx_name")]


class SpaceShip(Ship):
    warp_factor: float

    class ODMConfig(Document.ODMConfig):
        allow_inheritance = True


class StarfleetShip(SpaceShip):
    registry_number: str

    class ODMConfig(Document.ODMConfig):
        allow_inheritance = True
        indexes = [IndexModel([("registry_number", ASCENDING)], name="idx_registry")]


class Voyager(StarfleetShip):
    seven_on_board: bool

    class ODMConfig(Document.ODMConfig):
        allow_inheritance = False
