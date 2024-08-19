import typing

from BaseClasses import Item, ItemClassification
from worlds.AutoWorld import World
from types import SimpleNamespace

from worlds.dk64.DK64R.randomizer.Enums.Levels import Levels
from worlds.dk64.DK64R.randomizer.Lists import Item as DK64RItem
from worlds.dk64.DK64R.randomizer.Enums.Items import Items as DK64RItems
from worlds.dk64.DK64R.randomizer.Enums.Types import Types as DK64RTypes
import worlds.dk64.DK64R.randomizer.ItemPool as DK64RItemPoolUtility

BASE_ID = 0xD64000


class ItemData(typing.NamedTuple):
    code: typing.Optional[int]
    progression: bool
    quantity: int = 1
    event: bool = False


class DK64Item(Item):
    game: str = "Donkey Kong 64"


# Separate tables for each type of item.
junk_table = {

}

collectable_table = {

}

event_table = {
    "Victory": ItemData(0xD64000, True), # Temp
}

# Complete item table
full_item_table = { item.name: ItemData(int(BASE_ID + index), item.playthrough) for index, item in DK64RItem.ItemList.items() }

lookup_id_to_name: typing.Dict[int, str] = {data.code: item_name for item_name, data in full_item_table.items()}

full_item_table.update(event_table) # Temp for generating goal item


def setup_items(world: World) -> typing.List[DK64Item]:
    item_table = []
    
    # Figure out how many GB are progression - the Helm B. Locker is assumed to be the maximum value
    gb_item = DK64RItem.ItemList[DK64RItems.GoldenBanana]
    for i in range(min(161, world.logic_holder.settings.EntryGBs[Levels.HideoutHelm])):
        item_table.append(DK64Item(DK64RItems.GoldenBanana.name, ItemClassification.progression, full_item_table[gb_item.name], world.player))
    for i in range(161 - world.logic_holder.settings.EntryGBs[Levels.HideoutHelm]):
        item_table.append(DK64Item(DK64RItems.GoldenBanana.name, ItemClassification.useful, full_item_table[gb_item.name], world.player))
    # Figure out how many Medals are progression
    medal_item = DK64RItem.ItemList[DK64RItems.BananaMedal]
    for i in range(world.logic_holder.settings.medal_requirement):
        item_table.append(DK64Item(DK64RItems.BananaMedal.name, ItemClassification.progression, full_item_table[medal_item.name], world.player))
    for i in range(40 - world.logic_holder.settings.medal_requirement):
        item_table.append(DK64Item(DK64RItems.BananaMedal.name, ItemClassification.useful, full_item_table[medal_item.name], world.player))
    # Figure out how many Fairies are progression
    fairy_item = DK64RItem.ItemList[DK64RItems.BananaFairy]
    for i in range(world.logic_holder.settings.rareware_gb_fairies):
        item_table.append(DK64Item(DK64RItems.BananaFairy.name, ItemClassification.progression, full_item_table[fairy_item.name], world.player))
    for i in range(20 - world.logic_holder.settings.rareware_gb_fairies):
        item_table.append(DK64Item(DK64RItems.BananaFairy.name, ItemClassification.useful, full_item_table[fairy_item.name], world.player))

    all_shuffled_items = DK64RItemPoolUtility.GetItemsNeedingToBeAssumed(world.logic_holder.settings, [DK64RTypes.Medal, DK64RTypes.Fairy, DK64RTypes.Banana, DK64RTypes.ToughBanana], [])
    all_shuffled_items.extend(DK64RItemPoolUtility.JunkSharedMoves)

    for seed_item in all_shuffled_items:
        item = DK64RItem.ItemList[seed_item]
        if item.type in [DK64RItems.JunkCrystal, DK64RItems.JunkMelon, DK64RItems.JunkAmmo, DK64RItems.JunkFilm, DK64RItems.JunkOrange, DK64RItems.CrateMelon]:
            classification = ItemClassification.filler
        elif item.type in [DK64RItems.FakeItem]:
            classification = ItemClassification.trap
        # The playthrough tag doesn't quite 1-to-1 map to Archipelago's "progression" type - some items we don't consider "playthrough" can affect logic
        elif item.playthrough == True or item.type == DK64RTypes.Blueprint:
            classification = ItemClassification.progression
        else: # double check jetpac, eh?
            classification = ItemClassification.useful
        if seed_item == DK64RItems.HideoutHelmKey and world.logic_holder.settings.key_8_helm:
            world.multiworld.get_location("The End of Helm", world.player).place_locked_item(DK64Item("HideoutHelmKey", ItemClassification.progression, full_item_table[item.name], world.player))
            world.logic_holder.location_pool_size -= 1
        item_table.append(DK64Item(seed_item.name, classification, full_item_table[item.name], world.player))

    # if there's too many locations and not enough items, add some junk? Amount TBD, not sure how to precisely calculate this
    junk_item = DK64RItem.ItemList[DK64RItems.JunkMelon]
    print("location comparison: " + str(world.logic_holder.location_pool_size - 1))
    print("non-junk items: " + str(len(item_table)))
    if world.logic_holder.location_pool_size - len(item_table) - 1 < 0:
        raise Exception("Too many DK64 items to be placed in too few DK64 locations")
    for i in range(world.logic_holder.location_pool_size - len(item_table) - 1):  # The last 1 is for the Banana Hoard
        item_table.append(DK64Item(DK64RItems.JunkMelon.name, ItemClassification.filler, full_item_table[junk_item.name], world.player))
    print("projected available locations: " + str(world.logic_holder.location_pool_size - 1))
    print("projected items to place: " + str(len(item_table)))

    # Example of accessing Option result
    if world.options.goal == "krool":
        pass

    # DEBUG
    #for k, v in full_item_table.items():
    #    print(k + ": " + hex(v.code) + " | " + str(v.progression))

    return item_table
