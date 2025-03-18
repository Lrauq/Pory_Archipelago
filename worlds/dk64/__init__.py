import os
import sys
import typing
import math
import threading
import time
import json
import zipfile
import codecs
from io import BytesIO
sys.path.append('./worlds/dk64/DK64R/')

from BaseClasses import Item, MultiWorld, Tutorial, ItemClassification
from worlds.dk64.DK64R.randomizer.Enums.Items import Items as DK64RItems
from worlds.dk64.DK64R.randomizer.SettingStrings import decrypt_settings_string_enum
from .Items import DK64Item, full_item_table, setup_items
from .Options import GenerateDK64Options, dk64_options
from .Regions import all_locations, create_regions, connect_regions
from .Rules import set_rules
from worlds.AutoWorld import WebWorld, World
# import Patch
from .Logic import LogicVarHolder
from worlds.dk64.DK64R.randomizer.Spoiler import Spoiler
from worlds.dk64.DK64R.randomizer.Settings import Settings
from worlds.dk64.DK64R.randomizer.Patching.ApplyRandomizer import patching_response
from worlds.dk64.DK64R import version
from worlds.dk64.DK64R.randomizer.Patching.EnemyRando import randomize_enemies_0
from worlds.dk64.DK64R.randomizer.Fill import ShuffleItems, ItemReference
from worlds.dk64.DK64R.randomizer.CompileHints import compileMicrohints
from worlds.dk64.DK64R.randomizer.Enums.Types import Types
from worlds.dk64.DK64R.randomizer.Enums.Locations import Locations
from worlds.dk64.DK64R.randomizer.Lists.Location import PreGivenLocations
from worlds.LauncherComponents import Component, components, Type, icon_paths, local_path, launch as launch_component

def launch_client():
    from .DK64Client import launch
    launch_component(launch, name="DK64 Client")


components.append(Component("DK64 Client", "DK64Client", func=launch_client, component_type=Type.CLIENT, icon="dk64"))

icon_paths['dk64'] = local_path('worlds/dk64/dk64r/static/img/', 'dk.png')

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
        self.settings_string = "fjNPxAMxDIUx0QSpbHPUlZlBLg5gPQ+oBwRDIhKlsa58Iz8fiNEpEtiFKC4bVAhMF6AAd+AAOCAAGGAAGKAAAdm84FBiMhjoStwFIKW2wLcBJIBpkzVRCjFIKUUwGTLK/BQBuAIMAN4CBwBwAYQAOIECQByAoUAOYGCwB0A4YeXIITIagOrIrwAZTiU1QwkoSjuq1ZLEjQ0gRydoVFtRl6KiLAImIoArFljkbsl4u8igch2MvacgZ5GMGQBlU4IhAALhQALhgAJhwAJiAAHrQAHiQAFigADiwAHjAAFjQADrgALT5XoElypbPZZDCOZJ6Nh8Zq7WBgM5dVhVFZoKZUWjHFKAFBWDReUAnFRaJIuIZiTxrSyDSIjXR2AB0AvCoICQoLDA0OEBESFBUWGBkaHB0eICEiIyQlJicoKSorLC0uLzAxMjM0Nay+AMAAwgDEAJ0AsgBRAA"
        settings_dict = decrypt_settings_string_enum(self.settings_string)
        settings = Settings(settings_dict)
        spoiler = Spoiler(settings)
        spoiler.settings.shuffled_location_types.append(Types.ArchipelagoItem)
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
        # Handle enemy rando
        self.logic_holder.spoiler.enemy_rando_data = {}
        self.logic_holder.spoiler.pkmn_snap_data = []
        if self.logic_holder.spoiler.settings.enemy_rando:
            randomize_enemies_0(self.logic_holder.spoiler)

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
            self.logic_holder.spoiler.pregiven_items = []
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
                    if dk64_loc_id in PreGivenLocations:
                        if self.logic_holder.spoiler.settings.fast_start_beginning_of_game or dk64_loc_id != Locations.IslesFirstMove:
                            self.logic_holder.spoiler.pregiven_items.append(dk64_loc.item)
                        else:
                            self.logic_holder.spoiler.first_move_item = dk64_loc.item
                if dk64_location_id is not None and ap_location.item is not None:
                    ap_item = ap_location.item
                    if ap_item.player != self.player:
                        self.logic_holder.spoiler.LocationList[dk64_location_id].PlaceItem(self.logic_holder.spoiler, DK64RItems.ArchipelagoItem)  # TODO: replace with new AP item
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
            ShuffleItems(self.logic_holder.spoiler)
            self.logic_holder.spoiler.location_references = [
                # DK Moves
                ItemReference(DK64RItems.BaboonBlast, "Baboon Blast", "DK Japes Cranky"),
                ItemReference(DK64RItems.StrongKong, "Strong Kong", "DK Aztec Cranky"),
                ItemReference(DK64RItems.GorillaGrab, "Gorilla Grab", "DK Factory Cranky"),
                ItemReference(DK64RItems.Coconut, "Coconut Gun", "DK Japes Funky"),
                ItemReference(DK64RItems.Bongos, "Bongo Blast", "DK Aztec Candy"),
                # Diddy Moves
                ItemReference(DK64RItems.ChimpyCharge, "Chimpy Charge", "Diddy Japes Cranky"),
                ItemReference(DK64RItems.RocketbarrelBoost, "Rocketbarrel Boost", "Diddy Aztec Cranky"),
                ItemReference(DK64RItems.SimianSpring, "Simian Spring", "Diddy Factory Cranky"),
                ItemReference(DK64RItems.Peanut, "Peanut Popguns", "Diddy Japes Funky"),
                ItemReference(DK64RItems.Guitar, "Guitar Gazump", "Diddy Aztec Candy"),
                # Lanky Moves
                ItemReference(DK64RItems.Orangstand, "Orangstand", "Lanky Japes Cranky"),
                ItemReference(DK64RItems.BaboonBalloon, "Baboon Balloon", "Lanky Factory Cranky"),
                ItemReference(DK64RItems.OrangstandSprint, "Orangstand Sprint", "Lanky Caves Cranky"),
                ItemReference(DK64RItems.Grape, "Grape Shooter", "Lanky Japes Funky"),
                ItemReference(DK64RItems.Trombone, "Trombone Tremor", "Lanky Aztec Candy"),
                # Tiny Moves
                ItemReference(DK64RItems.MiniMonkey, "Mini Monkey", "Tiny Japes Cranky"),
                ItemReference(DK64RItems.PonyTailTwirl, "Pony Tail Twirl", "Tiny Factory Cranky"),
                ItemReference(DK64RItems.Monkeyport, "Monkeyport", "Tiny Caves Cranky"),
                ItemReference(DK64RItems.Feather, "Feather Bow", "Tiny Japes Funky"),
                ItemReference(DK64RItems.Saxophone, "Saxophone Slam", "Tiny Aztec Candy"),
                # Chunky Moves
                ItemReference(DK64RItems.HunkyChunky, "Hunky Chunky", "Chunky Japes Cranky"),
                ItemReference(DK64RItems.PrimatePunch, "Primate Punch", "Chunky Factory Cranky"),
                ItemReference(DK64RItems.GorillaGone, "Gorilla Gone", "Chunky Caves Cranky"),
                ItemReference(DK64RItems.Pineapple, "Pineapple Launcher", "Chunky Japes Funky"),
                ItemReference(DK64RItems.Triangle, "Triangle Trample", "Chunky Aztec Candy"),
                # Gun Upgrades
                ItemReference(DK64RItems.HomingAmmo, "Homing Ammo", "Shared Forest Funky"),
                ItemReference(DK64RItems.SniperSight, "Sniper Scope", "Shared Castle Funky"),
                ItemReference(DK64RItems.ProgressiveAmmoBelt, "Progressive Ammo Belt", ["Shared Factory Funky", "Shared Caves Funky"]),
                ItemReference(DK64RItems.Camera, "Fairy Camera", "Banana Fairy Gift"),
                ItemReference(DK64RItems.Shockwave, "Shockwave", "Banana Fairy Gift"),
                # Basic Moves
                ItemReference(DK64RItems.Swim, "Diving", "Dive Barrel"),
                ItemReference(DK64RItems.Oranges, "Orange Throwing", "Orange Barrel"),
                ItemReference(DK64RItems.Barrels, "Barrel Throwing", "Barrel Barrel"),
                ItemReference(DK64RItems.Vines, "Vine Swinging", "Vine Barrel"),
                ItemReference(DK64RItems.Climbing, "Climbing", "Starting Move"),
                # Instrument Upgrades & Slams
                ItemReference(
                    DK64RItems.ProgressiveInstrumentUpgrade,
                    "Progressive Instrument Upgrade",
                    ["Shared Galleon Candy", "Shared Caves Candy", "Shared Castle Candy"],
                ),
                ItemReference(
                    DK64RItems.ProgressiveSlam,
                    "Progressive Slam",
                    ["Shared Isles Cranky", "Shared Forest Cranky", "Shared Castle Cranky"],
                ),
                # Kongs
                ItemReference(DK64RItems.Donkey, "Donkey Kong", "Starting Kong"),
                ItemReference(DK64RItems.Diddy, "Diddy Kong", "Japes Diddy Cage"),
                ItemReference(DK64RItems.Lanky, "Lanky Kong", "Llama Lanky Cage"),
                ItemReference(DK64RItems.Tiny, "Tiny Kong", "Aztec Tiny Cage"),
                ItemReference(DK64RItems.Chunky, "Chunky Kong", "Factory Chunky Cage"),
                # Shopkeepers
                ItemReference(DK64RItems.Cranky, "Cranky Kong", "Starting Item"),
                ItemReference(DK64RItems.Candy, "Candy Kong", "Starting Item"),
                ItemReference(DK64RItems.Funky, "Funky Kong", "Starting Item"),
                ItemReference(DK64RItems.Snide, "Snide", "Starting Item"),
                # Early Keys
                ItemReference(DK64RItems.JungleJapesKey, "Key 1", "Starting Key"),
                ItemReference(DK64RItems.AngryAztecKey, "Key 2", "Starting Key"),
                ItemReference(DK64RItems.FranticFactoryKey, "Key 3", "Starting Key"),
                ItemReference(DK64RItems.GloomyGalleonKey, "Key 4", "Starting Key"),
                # Late Keys
                ItemReference(DK64RItems.FungiForestKey, "Key 5", "Starting Key"),
                ItemReference(DK64RItems.CrystalCavesKey, "Key 6", "Starting Key"),
                ItemReference(DK64RItems.CreepyCastleKey, "Key 7", "Starting Key"),
                ItemReference(DK64RItems.HideoutHelmKey, "Key 8", "Starting Key"),
            ]
            self.logic_holder.spoiler.UpdateLocations(self.logic_holder.spoiler.LocationList)
            compileMicrohints(self.logic_holder.spoiler)
            self.logic_holder.spoiler.majorItems = []
            patch_data, _ = patching_response(self.logic_holder.spoiler)
            self.logic_holder.spoiler.FlushAllExcessSpoilerData()
            patch_file = self.update_seed_results(patch_data, self.logic_holder.spoiler, self.player)
            print("output/" + f"{self.multiworld.get_out_file_name_base(self.player)}-dk64.lanky")
            with open("output/" + f"{self.multiworld.get_out_file_name_base(self.player)}-dk64.lanky", "w") as f:
                f.write(patch_file)
        except:
            raise
        finally:
            self.rom_name_available_event.set() # make sure threading continues and errors are collected

    def update_seed_results(self, patch, spoiler, player_id):
        """Update the seed results."""
        
        timestamp = time.time()
        hash = spoiler.settings.seed_hash
        spoiler_log = {}
        spoiler_log["Generated Time"] = timestamp
        # Zip all the data into a single file.
        zip_data = BytesIO()
        with zipfile.ZipFile(zip_data, "w") as zip_file:
            # Write each variable to the zip file
            zip_file.writestr("patch", patch)
            zip_file.writestr("hash", str(hash))
            zip_file.writestr("spoiler_log", str(json.dumps(spoiler_log)))
            zip_file.writestr("seed_id", str(spoiler.settings.seed_id))
            zip_file.writestr("generated_time", str(timestamp))
            zip_file.writestr("version", version.version)
            zip_file.writestr("seed_number", "archipelago-seed-" + str(player_id))
        zip_data.seek(0)
        # Convert the zip to a string of base64 data
        zip_conv = codecs.encode(zip_data.getvalue(), "base64").decode()

        return zip_conv

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
