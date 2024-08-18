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
    all_shuffled_items = DK64RItemPoolUtility.GetItemsNeedingToBeAssumed(world.logic_holder.settings, [DK64RTypes.ToughBanana], [])
    all_shuffled_items.extend(DK64RItemPoolUtility.ToughGoldenBananaItems())  # This weirdness is a 3.0 bug where Tough GBs are counted twice in the above method
    all_shuffled_items.extend(DK64RItemPoolUtility.JunkSharedMoves)
   
    for seed_item in all_shuffled_items:
        item = DK64RItem.ItemList[seed_item]
        if item.type in [DK64RItems.JunkCrystal, DK64RItems.JunkMelon, DK64RItems.JunkAmmo, DK64RItems.JunkFilm, DK64RItems.JunkOrange, DK64RItems.CrateMelon]:
            classification = ItemClassification.filler
        elif item.type in [DK64RItems.FakeItem]:
            classification = ItemClassification.trap
        elif item.playthrough == True or item.type == DK64RTypes.Blueprint:  # The playthrough tag doesn't quite 1-to-1 map to Archipelago's "progression" type
            classification = ItemClassification.progression
        else:
            classification = ItemClassification.useful
        if seed_item == DK64RItems.HideoutHelmKey and world.logic_holder.settings.key_8_helm:
            world.multiworld.get_location("The End of Helm", world.player).place_locked_item(DK64Item("Key 8", ItemClassification.progression, full_item_table[item.name], world.player))
        item_table.append(DK64Item(item.name, classification, full_item_table[item.name], world.player))
    
    # if there's too many locations and not enough items, add some junk? TBD
    print("projected available locations: " + str(world.logic_holder.location_pool_size))
    print("projected items to place: " + str(len(item_table)))

    # Example of accessing Option result
    if world.options.goal == "krool":
        pass

    # DEBUG
    #for k, v in full_item_table.items():
    #    print(k + ": " + hex(v.code) + " | " + str(v.progression))

    return item_table
