from typing import Optional

import pytest
from bson import ObjectId
from mongodb_odm import ASCENDING, Document, Field, ODMObjectId, Relationship
from mongodb_odm.connection import db
from mongodb_odm.utils.apply_indexes import apply_indexes

from tests.conftest import INIT_CONFIG
from tests.models.ship import Ship, SpaceShip, StarfleetShip, Voyager
from tests.utils import (
    TOTAL_SHIPS,
    TOTAL_SPACESHIPS,
    TOTAL_STARFLEET,
    TOTAL_VOYAGER,
    populate_ship_data,
)


@pytest.mark.usefixtures(INIT_CONFIG)
def test_multilevel_inheritance_find():
    populate_ship_data()

    all_ships = list(Ship.find())
    assert len(all_ships) == TOTAL_SHIPS

    assert len([s for s in all_ships if isinstance(s, SpaceShip)]) == TOTAL_SPACESHIPS
    assert (
        len([s for s in all_ships if isinstance(s, StarfleetShip)]) == TOTAL_STARFLEET
    )
    assert len([s for s in all_ships if isinstance(s, Voyager)]) == TOTAL_VOYAGER

    space_ships = list(SpaceShip.find())
    assert len(space_ships) == TOTAL_SPACESHIPS

    for s in space_ships:
        assert isinstance(s, SpaceShip)
        assert s.warp_factor > 0.0
        assert s.name != "Titanic"

    starfleet_ships = list(StarfleetShip.find())
    assert len(starfleet_ships) == TOTAL_STARFLEET

    for s in starfleet_ships:
        assert isinstance(s, StarfleetShip)
        assert s.registry_number is not None
        assert s.name != "Alien Ship"

    voyagers = list(Voyager.find())
    assert len(voyagers) == TOTAL_VOYAGER

    v = voyagers[0]
    assert isinstance(v, Voyager)
    assert v.name == "USS Voyager"
    assert v.warp_factor == 9.975
    assert v.registry_number == "NCC-74656"
    assert v.seven_on_board is True


@pytest.mark.usefixtures(INIT_CONFIG)
def test_multilevel_inheritance_find_one():
    populate_ship_data()

    obj = Ship.find_one({Ship.name: "Titanic"})
    assert isinstance(obj, Ship)
    assert not isinstance(obj, SpaceShip)

    obj = Ship.find_one({Ship.name: "USS Voyager"})
    assert isinstance(obj, Voyager)
    assert obj.registry_number == "NCC-74656"

    obj = SpaceShip.find_one({SpaceShip.name: "Titanic"})
    assert obj is None

    obj = SpaceShip.find_one({SpaceShip.name: "Alien Ship"})
    assert isinstance(obj, SpaceShip)
    assert not isinstance(obj, StarfleetShip)

    obj = SpaceShip.find_one({SpaceShip.name: "USS Enterprise"})
    assert isinstance(obj, StarfleetShip)
    assert not isinstance(obj, Voyager)
    assert obj.registry_number == "NCC-1701"

    obj = Voyager.find_one({Voyager.seven_on_board: True})
    assert isinstance(obj, Voyager)


@pytest.mark.usefixtures(INIT_CONFIG)
def test_multilevel_inheritance_get():
    populate_ship_data()

    obj = Ship.get({})
    assert isinstance(obj, Ship)

    obj = SpaceShip.get({})
    assert isinstance(obj, SpaceShip)

    obj = StarfleetShip.get({})
    assert isinstance(obj, StarfleetShip)

    obj = Voyager.get({})
    assert isinstance(obj, Voyager)


@pytest.mark.usefixtures(INIT_CONFIG)
def test_multilevel_inheritance_document_count():
    populate_ship_data()

    assert Ship.count_documents() == TOTAL_SHIPS
    assert SpaceShip.count_documents() == TOTAL_SPACESHIPS
    assert StarfleetShip.count_documents() == TOTAL_STARFLEET
    assert Voyager.count_documents() == TOTAL_VOYAGER


@pytest.mark.usefixtures(INIT_CONFIG)
def test_multilevel_inheritance_exists():
    populate_ship_data()

    assert Ship.exists() is True

    assert SpaceShip.exists() is True

    assert StarfleetShip.exists() is True

    assert Voyager.exists() is True

    StarfleetShip.delete_many({})

    assert Voyager.exists() is False

    assert StarfleetShip.exists() is False

    assert SpaceShip.exists() is True

    assert Ship.exists() is True


@pytest.mark.usefixtures(INIT_CONFIG)
def test_multilevel_inheritance_update_one():
    populate_ship_data()

    # Update Voyager via SpaceShip (Level 2) query
    SpaceShip.update_one(
        {SpaceShip.name: "USS Voyager"}, {"$set": {SpaceShip.warp_factor: 15.0}}
    )

    v = Voyager.get({})
    assert v.warp_factor == 15.0


@pytest.mark.usefixtures(INIT_CONFIG)
def test_multilevel_inheritance_child_aggregation():
    populate_ship_data()

    total_spaceships = 0
    for obj in SpaceShip.aggregate(pipeline=[]):
        assert isinstance(obj.id, ObjectId)
        total_spaceships += 1

    assert total_spaceships == TOTAL_SPACESHIPS


@pytest.mark.usefixtures(INIT_CONFIG)
def test_multilevel_inheritance_model_relation_load_related():
    class OtherModel(Document):
        title: str = Field(...)

    class ParentModel(Document):
        title: str = Field(...)

        class ODMConfig(Document.ODMConfig):
            allow_inheritance = True

    class ChildModel(ParentModel):
        child_title: str = Field(...)
        other_id: ODMObjectId = Field(...)

        other: Optional[OtherModel] = Relationship(local_field="other_id")

        class ODMConfig(Document.ODMConfig):
            allow_inheritance = True

    class GrandChildModel(ChildModel):
        grandchild_title: str = Field(...)

        class ODMConfig(Document.ODMConfig):
            allow_inheritance = False

    other = OtherModel(title="demo").create()

    ParentModel(title="demo").create()
    ChildModel(title="demo", child_title="demo", other_id=other.id).create()
    GrandChildModel(
        title="demo", child_title="demo", grandchild_title="demo", other_id=other.id
    ).create()

    parent_qs = ParentModel.find(sort=[(ParentModel.id, ASCENDING)])
    parents = ParentModel.load_related(parent_qs)

    assert len(parents) == 3, "Should have 3 objects"

    parent = parents[0]
    child = parents[1]
    grandchild = parents[2]

    assert isinstance(parent, ParentModel), "First object should be ParentModel"
    assert isinstance(child, ChildModel), "Second object should be ChildModel"
    assert isinstance(grandchild, GrandChildModel), (
        "Third object should be GrandChildModel"
    )

    assert not isinstance(child.other, OtherModel), (
        "The related field should not populate the child model fields when loading from parent model"
    )

    child_qs = ChildModel.find(sort=[(ChildModel.id, ASCENDING)])
    children = ChildModel.load_related(child_qs)

    assert len(children) == 2, "Should have 2 objects"

    child = children[0]
    grandchild = children[1]

    assert isinstance(child, ChildModel), "First object should be ChildModel"
    assert isinstance(grandchild, GrandChildModel), (
        "Second object should be GrandChildModel"
    )

    assert isinstance(child.other, OtherModel), "Related field should be populated"
    assert child.other.title == "demo", "Related field should have correct data"

    grandchild_qs = GrandChildModel.find(sort=[(GrandChildModel.id, ASCENDING)])
    grandchildren = GrandChildModel.load_related(grandchild_qs)

    assert len(grandchildren) == 1, "Should have 1 object"

    grandchild = grandchildren[0]

    assert isinstance(grandchild, GrandChildModel), (
        "First object should be GrandChildModel"
    )

    assert isinstance(grandchild.other, OtherModel), "Related field should be populated"
    assert grandchild.other.title == "demo", "Related field should have correct data"


@pytest.mark.usefixtures(INIT_CONFIG)
def test_index_and_collection_propagation():
    populate_ship_data()
    apply_indexes()

    target_coll = db().ship_multilevel_collection
    assert target_coll.count_documents({}) == TOTAL_SHIPS

    doc = target_coll.find_one({Voyager.seven_on_board: True})
    assert doc["_cls"] == "voyager"

    indexes = list(target_coll.list_indexes())
    index_names = [idx["name"] for idx in indexes]

    assert "idx_name" in index_names
    assert "idx_registry" in index_names
