import os
import sys
import typing
import math
import threading
# Print the original running script
original_file = os.path.basename(sys.argv[0])
if not "DK64Client" in original_file:
    sys.path.append('./worlds/dk64/DK64R/')

    from BaseClasses import Item, MultiWorld, Tutorial, ItemClassification
    from worlds.dk64.DK64R.randomizer.Enums.Items import Items as DK64RItems
    from worlds.dk64.DK64R.randomizer.SettingStrings import decrypt_settings_string_enum
    from .Items import DK64Item, full_item_table, setup_items
    from .Options import GenerateDK64Options, dk64_options
    from .Regions import all_locations, create_regions, connect_regions
    from .Rules import set_rules
    from worlds.AutoWorld import WebWorld, World
    import Patch
    from .Logic import LogicVarHolder
    from worlds.dk64.DK64R.randomizer.Spoiler import Spoiler
    from worlds.dk64.DK64R.randomizer.Settings import Settings

    class DK64Web(WebWorld):
        theme = "jungle"

        setup_en = Tutorial(
            "Multiworld Setup Guide",
            "A guide to setting up the Donkey Kong 64 randomizer connected to an Archipelago Multiworld.",
            "English",
            "setup_en.md",
            "setup/en",
            ["PoryGone"]
        )

        tutorials = [setup_en]


    class DK64World(World):
        """
        Donkey Kong 64 is a 3D collectathon platforming game.
        Play as the whole DK Crew and rescue the Golden Banana hoard from King K. Rool.
        """
        game: str = "Donkey Kong 64"
        #option_definitions = dk64_options
        option_definitions = GenerateDK64Options()
        topology_present = False
        data_version = 0

        item_name_to_id = {name: data.code for name, data in full_item_table.items()}
        location_name_to_id = all_locations

        web = DK64Web()


        def __init__(self, multiworld: MultiWorld, player: int):
            self.rom_name_available_event = threading.Event()
            super().__init__(multiworld, player)
            self.settings_string = "fjNPxAMxDIUx0QSpbHPUlZlBLg5gPQ+oBwRDIhKlsa58Iz8fiNEpEtiFKi4bVAhMF6AAd+AAOCAAGGAAGKAAAdm84FBiMhjoStwFIKW2wLcBJIBpkzVRCjFIKUUwGTLK/BQBuAIMAN4CBwBwAYQAOIECQByAoUAOYGCwB0A4YeXIITIagOrIrwAZTiU1QwkoSjuq1ZLEjQ0gRydoVFtRl6KiLAImIoArFljkbsl4u8igch2MvacgZ5GMGQBlU4IhAALhQALhgAJhwAJiAAHrQAHiQAFigADiwAHjAAFjQADrgALT5XoElypbPZZDCOZJ6Nh8Zq7WBgM5dVhVFZoKZUWjHFKAFBWDReUAnFRaJIuIZiTxrSyDSIjXR2AB0AvCoICQoLDA0OEBESFBUWGBkaHB0eICEiIyQlJicoKSorLC0uLzAxMjM0Nay+AMAAwgDEAJ0AsgBRAA"
            settings_dict = decrypt_settings_string_enum(self.settings_string)
            settings = Settings(settings_dict)
            spoiler = Spoiler(settings)
            self.logic_holder = LogicVarHolder(spoiler, self)

        @classmethod
        def stage_assert_generate(cls, multiworld: MultiWorld):
            #rom_file = get_base_rom_path()
            #if not os.path.exists(rom_file):
            #    raise FileNotFoundError(rom_file)
            pass

        def _get_slot_data(self):
            return {
                #"death_link": self.options.death_link.value,
            }

        def generate_early(self):
            # handle starting moves?
            pass

        def create_regions(self) -> None:
            create_regions(self.multiworld, self.player, self.logic_holder)

        def create_items(self) -> None:
            itempool: typing.List[DK64Item] = setup_items(self)
            self.multiworld.itempool += itempool

        def set_rules(self):
            set_rules(self.multiworld, self.player)

        def generate_basic(self):
            connect_regions(self, self.logic_holder)

            self.multiworld.get_location("Banana Hoard", self.player).place_locked_item(DK64Item("BananaHoard", ItemClassification.progression, 0x000000, self.player)) # TEMP?

        def generate_output(self, output_directory: str):
            try:
                # Read through all item assignments in this AP world and find their DK64 equivalents so we can update our world state for patching purposes
                for ap_location in self.multiworld.get_locations(self.player):
                    # We never need to place Collectibles or Events in our world state
                    if "Collectible" in ap_location.name or "Event" in ap_location.name:
                        continue
                    # Find the corresponding DK64 Locations enum
                    dk64_location_id = None
                    for dk64_loc_id, dk64_loc in self.logic_holder.spoiler.LocationList.items():
                        if dk64_loc.name == ap_location.name:
                            dk64_location_id = dk64_loc_id
                            break
                    if dk64_location_id is not None and ap_location.item is not None:
                        ap_item = ap_location.item
                        if ap_item.player != self.player:
                            self.logic_holder.spoiler.LocationList[dk64_location_id].PlaceItem(self.logic_holder.spoiler, DK64RItems.TestItem)  # TODO: replace with new AP item
                        elif "Collectible" in ap_item.name:
                            continue
                        else:
                            dk64_item = DK64RItems[ap_item.name]
                            if dk64_item is not None:
                                self.logic_holder.spoiler.LocationList[dk64_location_id].PlaceItem(self.logic_holder.spoiler, dk64_item)
                            else:
                                print(f"Item {ap_item.name} not found in DK64 item table.")
                    elif dk64_location_id is not None:
                        self.logic_holder.spoiler.LocationList[dk64_location_id].PlaceItem(self.logic_holder.spoiler, DK64RItems.NoItem)
                    else:
                        print(f"Location {ap_location.name} not found in DK64 location table.")

                rompath = os.path.join(output_directory, f"{self.multiworld.get_out_file_name_base(self.player)}.sfc")
            except:
                raise
            finally:
                if os.path.exists(rompath):
                    os.unlink(rompath)
                self.rom_name_available_event.set() # make sure threading continues and errors are collected

        def modify_multidata(self, multidata: dict):
            pass

        def fill_slot_data(self) -> dict:
            slot_data = self._get_slot_data()
            for option_name in dk64_options:
                option = getattr(self.multiworld, option_name)[self.player]
                slot_data[option_name] = option.value

            return slot_data

        def create_item(self, name: str, force_non_progression=False) -> Item:
            data = full_item_table[name]

            if force_non_progression:
                classification = ItemClassification.filler
            elif data.progression:
                classification = ItemClassification.progression
            else:
                classification = ItemClassification.filler

            created_item = DK64Item(name, classification, data.code, self.player)

            return created_item
