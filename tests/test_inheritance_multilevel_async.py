from typing import Optional

import pytest
from bson import ObjectId
from mongodb_odm import ASCENDING, Document, Field, ODMObjectId, Relationship
from mongodb_odm.connection import db
from mongodb_odm.utils.apply_indexes import async_apply_indexes

from tests.conftest import ASYNC_INIT_CONFIG
from tests.models.ship import Ship, SpaceShip, StarfleetShip, Voyager
from tests.utils import (
    TOTAL_SHIPS,
    TOTAL_SPACESHIPS,
    TOTAL_STARFLEET,
    TOTAL_VOYAGER,
    async_populate_ship_data,
)


@pytest.mark.usefixtures(ASYNC_INIT_CONFIG)
async def test_multilevel_inheritance_find():
    await async_populate_ship_data()

    all_ships = [s async for s in Ship.afind()]
    assert len(all_ships) == TOTAL_SHIPS

    assert len([s for s in all_ships if isinstance(s, SpaceShip)]) == TOTAL_SPACESHIPS
    assert (
        len([s for s in all_ships if isinstance(s, StarfleetShip)]) == TOTAL_STARFLEET
    )
    assert len([s for s in all_ships if isinstance(s, Voyager)]) == TOTAL_VOYAGER

    space_ships = [s async for s in SpaceShip.afind()]
    assert len(space_ships) == TOTAL_SPACESHIPS

    for s in space_ships:
        assert isinstance(s, SpaceShip)
        assert s.warp_factor > 0.0
        assert s.name != "Titanic"

    starfleet_ships = [s async for s in StarfleetShip.afind()]
    assert len(starfleet_ships) == TOTAL_STARFLEET

    for s in starfleet_ships:
        assert isinstance(s, StarfleetShip)
        assert s.registry_number is not None
        assert s.name != "Alien Ship"

    voyagers = [s async for s in Voyager.afind()]
    assert len(voyagers) == TOTAL_VOYAGER

    v = voyagers[0]
    assert isinstance(v, Voyager)
    assert v.name == "USS Voyager"
    assert v.warp_factor == 9.975
    assert v.registry_number == "NCC-74656"
    assert v.seven_on_board is True


@pytest.mark.usefixtures(ASYNC_INIT_CONFIG)
async def test_multilevel_inheritance_find_one():
    await async_populate_ship_data()

    obj = await Ship.afind_one({Ship.name: "Titanic"})
    assert isinstance(obj, Ship)
    assert not isinstance(obj, SpaceShip)

    obj = await Ship.afind_one({Ship.name: "USS Voyager"})
    assert isinstance(obj, Voyager)
    assert obj.registry_number == "NCC-74656"

    obj = await SpaceShip.afind_one({SpaceShip.name: "Titanic"})
    assert obj is None

    obj = await SpaceShip.afind_one({SpaceShip.name: "Alien Ship"})
    assert isinstance(obj, SpaceShip)
    assert not isinstance(obj, StarfleetShip)

    obj = await SpaceShip.afind_one({SpaceShip.name: "USS Enterprise"})
    assert isinstance(obj, StarfleetShip)
    assert not isinstance(obj, Voyager)
    assert obj.registry_number == "NCC-1701"

    obj = await Voyager.afind_one({Voyager.seven_on_board: True})
    assert isinstance(obj, Voyager)


@pytest.mark.usefixtures(ASYNC_INIT_CONFIG)
async def test_multilevel_inheritance_get():
    await async_populate_ship_data()

    obj = await Ship.aget({})
    assert isinstance(obj, Ship)

    obj = await SpaceShip.aget({})
    assert isinstance(obj, SpaceShip)

    obj = await StarfleetShip.aget({})
    assert isinstance(obj, StarfleetShip)

    obj = await Voyager.aget({})
    assert isinstance(obj, Voyager)


@pytest.mark.usefixtures(ASYNC_INIT_CONFIG)
async def test_multilevel_inheritance_document_count():
    await async_populate_ship_data()

    assert await Ship.acount_documents() == TOTAL_SHIPS
    assert await SpaceShip.acount_documents() == TOTAL_SPACESHIPS
    assert await StarfleetShip.acount_documents() == TOTAL_STARFLEET
    assert await Voyager.acount_documents() == TOTAL_VOYAGER


@pytest.mark.usefixtures(ASYNC_INIT_CONFIG)
async def test_multilevel_inheritance_exists():
    await async_populate_ship_data()

    assert await Ship.aexists() is True

    assert await SpaceShip.aexists() is True

    assert await StarfleetShip.aexists() is True

    assert await Voyager.aexists() is True

    await StarfleetShip.adelete_many({})

    assert await Voyager.aexists() is False

    assert await StarfleetShip.aexists() is False

    assert await SpaceShip.aexists() is True

    assert await Ship.aexists() is True


@pytest.mark.usefixtures(ASYNC_INIT_CONFIG)
async def test_multilevel_inheritance_update_one():
    await async_populate_ship_data()

    # Update Voyager via SpaceShip (Level 2) query
    await SpaceShip.aupdate_one(
        {SpaceShip.name: "USS Voyager"}, {"$set": {SpaceShip.warp_factor: 15.0}}
    )

    v = await Voyager.aget({})
    assert v.warp_factor == 15.0


@pytest.mark.usefixtures(ASYNC_INIT_CONFIG)
async def test_multilevel_inheritance_child_aggregation():
    await async_populate_ship_data()

    total_spaceships = 0
    async for obj in SpaceShip.aaggregate(pipeline=[]):
        assert isinstance(obj.id, ObjectId)
        total_spaceships += 1

    assert total_spaceships == TOTAL_SPACESHIPS


@pytest.mark.usefixtures(ASYNC_INIT_CONFIG)
async def test_multilevel_inheritance_model_relation_load_related():
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

    other = await OtherModel(title="demo").acreate()

    await ParentModel(title="demo").acreate()
    await ChildModel(title="demo", child_title="demo", other_id=other.id).acreate()
    await GrandChildModel(
        title="demo", child_title="demo", grandchild_title="demo", other_id=other.id
    ).acreate()

    parent_qs = ParentModel.afind(sort=[(ParentModel.id, ASCENDING)])
    parents = await ParentModel.aload_related(parent_qs)

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

    child_qs = ChildModel.afind(sort=[(ChildModel.id, ASCENDING)])
    children = await ChildModel.aload_related(child_qs)

    assert len(children) == 2, "Should have 2 objects"

    child = children[0]
    grandchild = children[1]

    assert isinstance(child, ChildModel), "First object should be ChildModel"
    assert isinstance(grandchild, GrandChildModel), (
        "Second object should be GrandChildModel"
    )

    assert isinstance(child.other, OtherModel), "Related field should be populated"
    assert child.other.title == "demo", "Related field should have correct data"

    grandchild_qs = GrandChildModel.afind(sort=[(GrandChildModel.id, ASCENDING)])
    grandchildren = await GrandChildModel.aload_related(grandchild_qs)

    assert len(grandchildren) == 1, "Should have 1 object"

    grandchild = grandchildren[0]

    assert isinstance(grandchild, GrandChildModel), (
        "First object should be GrandChildModel"
    )

    assert isinstance(grandchild.other, OtherModel), "Related field should be populated"
    assert grandchild.other.title == "demo", "Related field should have correct data"


@pytest.mark.usefixtures(ASYNC_INIT_CONFIG)
async def test_index_and_collection_propagation():
    await async_populate_ship_data()
    await async_apply_indexes()

    target_coll = db(is_async_action=True).ship_multilevel_collection
    assert await target_coll.count_documents({}) == TOTAL_SHIPS

    doc = await target_coll.find_one({Voyager.seven_on_board: True})
    assert doc["_cls"] == "voyager"

    cursor = await target_coll.list_indexes()
    indexes = [idx async for idx in cursor]

    index_names = [idx["name"] for idx in indexes]

    assert "idx_name" in index_names
    assert "idx_registry" in index_names
