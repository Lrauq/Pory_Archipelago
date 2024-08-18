import typing

from BaseClasses import CollectionState, ItemClassification, MultiWorld, Region, Entrance, Location
from worlds.AutoWorld import World

from worlds.dk64.DK64R.randomizer.Enums.Collectibles import Collectibles
from worlds.dk64.DK64R.randomizer.Enums.Events import Events
from worlds.dk64.DK64R.randomizer.Enums.Levels import Levels
from worlds.dk64.DK64R.randomizer.Enums.Locations import Locations
from worlds.dk64.DK64R.randomizer.Enums.Settings import HelmSetting
from worlds.dk64.DK64R.randomizer.Enums.Types import Types
from worlds.dk64.DK64R.randomizer.Lists import Location as DK64RLocation, Item as DK64RItem
from worlds.dk64.DK64R.randomizer.LogicClasses import Collectible, Event, LocationLogic, TransitionFront
from worlds.dk64.Items import DK64Item
from worlds.generic.Rules import set_rule
from .Logic import LogicVarHolder
from worlds.dk64.DK64R.randomizer.LogicFiles import (
    AngryAztec,
    CreepyCastle,
    CrystalCaves,
    DKIsles,
    FungiForest,
    HideoutHelm,
    JungleJapes,
    FranticFactory,
    GloomyGalleon,
    Shops,
)
from worlds.dk64.DK64R.randomizer.CollectibleLogicFiles import (
    AngryAztec as AztecCollectibles,
    CreepyCastle as CastleCollectibles,
    CrystalCaves as CavesCollectibles,
    DKIsles as IslesCollectibles,
    FungiForest as ForestCollectibles,
    JungleJapes as JapesCollectibles,
    FranticFactory as FactoryCollectibles,
    GloomyGalleon as GalleonCollectibles,
)

BASE_ID = 0xD64000


class DK64Location(Location):
    game: str = "Donkey Kong 64"

    def __init__(self, player: int, name: str = "", address: int = None, parent=None):
        super().__init__(player, name, address, parent)


# Complete location table
all_locations = {location.name: (BASE_ID + index) for index, location in enumerate(DK64RLocation.LocationListOriginal)}
all_locations.update({"Victory": 0x00})  # Temp for generating goal location
lookup_id_to_name: typing.Dict[int, str] = {id: name for name, id in all_locations.items()}

all_collectible_regions = {
        **AztecCollectibles.LogicRegions,
        **CastleCollectibles.LogicRegions,
        **CavesCollectibles.LogicRegions,
        **IslesCollectibles.LogicRegions,
        **ForestCollectibles.LogicRegions,
        **JapesCollectibles.LogicRegions,
        **FactoryCollectibles.LogicRegions,
        **GalleonCollectibles.LogicRegions,
    }
all_logic_regions = {
        **AngryAztec.LogicRegions,
        **CreepyCastle.LogicRegions,
        **CrystalCaves.LogicRegions,
        **DKIsles.LogicRegions,
        **FungiForest.LogicRegions,
        **HideoutHelm.LogicRegions,
        **JungleJapes.LogicRegions,
        **FranticFactory.LogicRegions,
        **GloomyGalleon.LogicRegions,
        **Shops.LogicRegions,
}


def create_regions(multiworld: MultiWorld, player: int, logic_holder: LogicVarHolder):
    menu_region = Region("Menu", player, multiworld)
    multiworld.regions.append(menu_region)
    
    for region_id in all_logic_regions:
        region_obj = all_logic_regions[region_id]
        location_logics = [loc for loc in region_obj.locations if not loc.isAuxiliaryLocation]
        collectibles = []
        if region_id in all_collectible_regions.keys():
            collectibles = [col for col in all_collectible_regions[region_id] if col.type in (Collectibles.bunch, Collectibles.banana, Collectibles.balloon)]
        events = [event for event in region_obj.events]
        multiworld.regions.append(create_region(multiworld, player, region_id.name, region_obj.level, location_logics, collectibles, events, logic_holder))


def create_region(multiworld: MultiWorld, player: int, region_name: str, level: Levels, location_logics: typing.List[LocationLogic], collectibles: typing.List[Collectible], events: typing.List[Event], logic_holder: LogicVarHolder) -> Region:
    new_region = Region(region_name, player, multiworld)

    if location_logics and region_name != "GameStart":  # Game start has no actual locations - starting moves are handled by Arch elsewhere
        for location_logic in location_logics:
            location_obj = DK64RLocation.LocationListOriginal[location_logic.id]
            # Starting move locations and Kongs may be shuffled but their locations are not relevant ever due to item placement restrictions
            if location_obj.type in (Types.TrainingBarrel, Types.PreGivenMove, Types.Kong):
                continue
            # Dropsanity would otherwise flood the world with irrelevant locked locations, greatly slowing seed gen
            if location_obj.type == Types.Enemies and Types.Enemies not in logic_holder.settings.shuffled_location_types:
                continue
            loc_id = all_locations.get(location_obj.name, 0)
            location = DK64Location(player, location_obj.name, loc_id, new_region)
            # If the location is not shuffled, lock in the default item on the location
            if location_logic.id != Locations.BananaHoard and location_obj.type not in logic_holder.settings.shuffled_location_types and location_obj.default is not None:
                location.address = None
                location.place_locked_item(DK64Item(DK64RItem.ItemList[location_obj.default].name, ItemClassification.progression, None, player))
            # Otherwise, this is a location that can have items in it, and counts towards the number of locations available for items
            else:
                logic_holder.location_pool_size += 1
            set_rule(location, lambda state, location_logic=location_logic: hasDK64RLocation(state, logic_holder, location_logic))
            new_region.locations.append(location)

    collectible_id = 0
    for collectible in collectibles:
        collectible_id += 1
        location_name = region_name + " Collectible " + str(collectible_id) +  ": " + collectible.kong.name + " " + collectible.type.name
        location = DK64Location(player, location_name, None, new_region)
        set_rule(location, lambda state, collectible=collectible: hasDK64RCollectible(state, logic_holder, collectible))
        quantity = collectible.amount
        if collectible.type == Collectibles.bunch:
            quantity *= 5
        elif collectible.type == Collectibles.balloon:
            quantity *= 10
        location.place_locked_item(DK64Item("Collectible CBs, " + collectible.kong.name + ", " + level.name + ", " + str(quantity), ItemClassification.progression, None, player))
        new_region.locations.append(location)
    
    for event in events:
        # Some events don't matter due to Archipelago settings
        # Most water level altering events are inaccessible, only the one specifically in LighthouseUnderwater is accessible
        if event.name in (Events.WaterLowered, Events.WaterRaised) and region_name != "LighthouseUnderwater":
            continue
        # This HelmFinished event is only necessary for skip all Helm
        if event.name == Events.HelmFinished and region_name == "HideoutHelmEntry" and logic_holder.settings.helm_setting != HelmSetting.skip_all:
            continue
        location_name = region_name + " Event " + event.name.name
        location = DK64Location(player, location_name, None, new_region)
        set_rule(location, lambda state, event=event: hasDK64REvent(state, logic_holder, event))
        location.place_locked_item(DK64Item("Event, " + event.name.name, ItemClassification.progression, None, player))
        new_region.locations.append(location)
    
    return new_region


def connect_regions(world: World, logic_holder: LogicVarHolder):
    connect(world, "Menu", "GameStart")

    # # Example Region Connection
    # connect(
    #     world,
    #     "DK Isles",
    #     "Test",
    #     lambda state: state.has(DK64RItem.ItemList[DK64RItems.GoldenBanana].name, world.player, 2),
    # )

    for region_id, region_obj in all_logic_regions.items():
        for exit in region_obj.exits:
            try:
                converted_logic = lambda state, exit=exit: hasDK64RTransition(state, logic_holder, exit)
                connect(world, region_id.name, exit.dest.name, converted_logic)
            except Exception:
                pass
    pass


def connect(world: World, source: str, target: str, rule: typing.Optional[typing.Callable] = None):
    source_region = world.multiworld.get_region(source, world.player)
    target_region = world.multiworld.get_region(target, world.player)

    name = source + "->" + target
    connection = Entrance(world.player, name, source_region)

    if rule:
        connection.access_rule = rule

    source_region.exits.append(connection)
    connection.connect(target_region)


def hasDK64RTransition(state: CollectionState, logic: LogicVarHolder, exit: TransitionFront):
    logic.UpdateFromArchipelagoItems(state)
    return exit.logic(logic)


def hasDK64RLocation(state: CollectionState, logic: LogicVarHolder, location: LocationLogic):
    try:
        quick_success = location.logic(None)
        if quick_success:
            return True
    except:
        pass
    logic.UpdateFromArchipelagoItems(state)
    return location.logic(logic)


def hasDK64RCollectible(state: CollectionState, logic: LogicVarHolder, collectible: Collectible):
    try:
        quick_success = collectible.logic(None)
        if quick_success:
            return True
    except:
        pass
    logic.UpdateFromArchipelagoItems(state)
    return collectible.logic(logic)


def hasDK64REvent(state: CollectionState, logic: LogicVarHolder, event: Event):
    try:
        quick_success = event.logic(None)
        if quick_success:
            return True
    except:
        pass
    logic.UpdateFromArchipelagoItems(state)
    return event.logic(logic)
