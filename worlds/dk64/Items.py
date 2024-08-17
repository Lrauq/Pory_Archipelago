import typing

from BaseClasses import Item, ItemClassification
from worlds.AutoWorld import World
from types import SimpleNamespace

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

    world.item_pool_size = 0  # Must match the number of locations created
    if not world.logic_holder.settings.shuffle_items:
        raise Exception("DK64 Settings must enable the item randomizer.")
    if DK64RTypes.Banana not in world.logic_holder.settings.shuffled_location_types:
        raise Exception("DK64 Settings must shuffle GBs.")
    world.item_pool_size = 161 - DK64RItemPoolUtility.TOUGH_BANANA_COUNT
    if DK64RTypes.Shop not in world.logic_holder.settings.shuffled_location_types:
        raise Exception("DK64 Settings must shuffle moves.")
    world.item_pool_size += len(DK64RItemPoolUtility.AllKongMoves()) + len(DK64RItemPoolUtility.JunkSharedMoves)
    if DK64RTypes.ToughBanana in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += DK64RItemPoolUtility.TOUGH_BANANA_COUNT
    if DK64RTypes.Blueprint in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += 40
    if DK64RTypes.Fairy in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += 20
    if DK64RTypes.Key in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += 8
    if DK64RTypes.Crown in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += 10
    if DK64RTypes.Coin in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += 2
    if DK64RTypes.TrainingBarrel in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += 4
    if DK64RTypes.Kong in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += 5
    if DK64RTypes.Medal in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += 40
    if DK64RTypes.Shockwave in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += 2
    if DK64RTypes.Bean in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += 1
    if DK64RTypes.Pearl in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += 5
    if DK64RTypes.RainbowCoin in world.logic_holder.settings.shuffled_location_types:
        world.item_pool_size += 16
    # might not even use this guy, might be able to sort this out another way

    all_shuffled_items = DK64RItemPoolUtility.GetItemsNeedingToBeAssumed(world.logic_holder.settings, [], [])
   
    for seed_item in all_shuffled_items:
        item = DK64RItem.ItemList[seed_item]
        if item.type in [DK64RItems.JunkCrystal, DK64RItems.JunkMelon, DK64RItems.JunkAmmo, DK64RItems.JunkFilm, DK64RItems.JunkOrange, DK64RItems.CrateMelon]:
            classification = ItemClassification.filler
        elif item.type in [DK64RItems.FakeItem]:
            classification = ItemClassification.trap
        elif item.playthrough == True:
            classification = ItemClassification.progression
        else:
            classification = ItemClassification.useful
        item_table.append(DK64Item(item.name, classification, full_item_table[item.name], world.player))
    
    # if there's too many locations and not enough items, add some junk?

    # Example of accessing Option result
    if world.options.goal == "krool":
        pass

    # DEBUG
    #for k, v in full_item_table.items():
    #    print(k + ": " + hex(v.code) + " | " + str(v.progression))

    return item_table
