import os
import typing
import math
import threading

from BaseClasses import Item, MultiWorld, Tutorial, ItemClassification
from .Items import DKC3Item, ItemData, item_table, inventory_table
from .Locations import DKC3Location, all_locations, setup_locations
from .Options import dkc3_options
from .Regions import create_regions, connect_regions
from .Levels import level_list
from .Rules import set_rules
from .Names import ItemName, LocationName
from ..AutoWorld import WebWorld, World
from .Rom import LocalRom, patch_rom, get_base_rom_path
import Patch


class DKC3Web(WebWorld):
    theme = "jungle"

    setup_en = Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up the Donkey Kong Country 3 randomizer connected to an Archipelago Multiworld.",
        "English",
        "setup_en.md",
        "setup/en",
        ["PoryGone"]
    )
    
    tutorials = [setup_en]


class DKC3World(World):
    """
    Donkey Kong Country 3 is an action platforming game.
    """
    game: str = "Donkey Kong Country 3"
    options = dkc3_options
    topology_present = False
    data_version = 1
    #hint_blacklist = {LocationName.rocket_rush_flag}

    item_name_to_id = {name: data.code for name, data in item_table.items()}
    location_name_to_id = all_locations

    active_level_list: typing.List[str]
    web = DKC3Web()
    
    def __init__(self, world: MultiWorld, player: int):
        self.rom_name_available_event = threading.Event()
        super().__init__(world, player)

    @classmethod
    def stage_assert_generate(cls, world):
        rom_file = get_base_rom_path()
        if not os.path.exists(rom_file):
            raise FileNotFoundError(rom_file)

    def _get_slot_data(self):
        return {
            #"death_link": self.world.death_link[self.player].value,
            "active_levels": self.active_level_list,
        }

    def _create_items(self, name: str):
        data = item_table[name]
        return [self.create_item(name)] * data.quantity

    def fill_slot_data(self) -> dict:
        slot_data = self._get_slot_data()
        for option_name in dkc3_options:
            option = getattr(self.world, option_name)[self.player]
            slot_data[option_name] = option.value

        return slot_data

    def generate_basic(self):
        self.topology_present = self.world.level_shuffle[self.player].value
        itempool: typing.List[DKC3Item] = []

        # Levels
        total_required_locations = 161

        number_of_banana_birds = 0
        number_of_cogs = 5
        number_of_bosses = 8
        if self.world.goal[self.player] == "knautilus":
            self.world.get_location(LocationName.kastle_kaos, self.player).place_locked_item(self.create_item(ItemName.victory))
            self.world.get_location(LocationName.rocket_rush_flag, self.player).place_locked_item(self.create_item(ItemName.krematoa_cog))
            number_of_cogs = 4
            number_of_bosses = 7

            # Rocket Rush Cog
            total_required_locations -= 1
        else:
            self.world.get_location(LocationName.banana_bird_mother, self.player).place_locked_item(self.create_item(ItemName.victory))
            number_of_banana_birds = self.world.number_of_banana_birds[self.player]

        # Bosses
        total_required_locations += number_of_bosses
        
        # Secret Caves
        total_required_locations += 13

        ## Brothers Bear
        if False:#self.world.include_trade_sequence[self.player]:
            total_required_locations += 8

        number_of_bonus_coins = (self.world.krematoa_bonus_coin_cost[self.player] * 5)
        number_of_bonus_coins += math.ceil((85 - number_of_bonus_coins) * self.world.percentage_of_extra_bonus_coins[self.player] / 100)

        itempool += [self.create_item(ItemName.bonus_coin)] * number_of_bonus_coins
        itempool += [self.create_item(ItemName.dk_coin)] * 41
        itempool += [self.create_item(ItemName.banana_bird)] * number_of_banana_birds
        itempool += [self.create_item(ItemName.krematoa_cog)] * number_of_cogs
        itempool += [self.create_item(ItemName.progressive_boat)] * 3

        total_junk_count = total_required_locations - len(itempool)

        itempool += [self.create_item(ItemName.bear_coin)] * total_junk_count

        self.active_level_list = level_list.copy()

        if self.world.level_shuffle[self.player]:
            self.world.random.shuffle(self.active_level_list)

        connect_regions(self.world, self.player, self.active_level_list)

        self.world.itempool += itempool

    def generate_output(self, output_directory: str):
        try:
            world = self.world
            player = self.player

            rom = LocalRom(get_base_rom_path())
            patch_rom(self.world, rom, self.player, self.active_level_list)

            self.active_level_list.append(LocationName.rocket_rush_region)
        
            outfilepname = f'_P{player}'
            outfilepname += f"_{world.player_name[player].replace(' ', '_')}" \
                if world.player_name[player] != 'Player%d' % player else ''

            rompath = os.path.join(output_directory, f'AP_{world.seed_name}{outfilepname}.sfc')
            rom.write_to_file(rompath)
            Patch.create_patch_file(rompath, player=player, player_name=world.player_name[player], game=Patch.GAME_DKC3)
            os.unlink(rompath)
            self.rom_name = rom.name
        except:
            raise
        finally:
            self.rom_name_available_event.set() # make sure threading continues and errors are collected

    def modify_multidata(self, multidata: dict):
        import base64
        # wait for self.rom_name to be available.
        self.rom_name_available_event.wait()
        rom_name = getattr(self, "rom_name", None)
        # we skip in case of error, so that the original error in the output thread is the one that gets raised
        if rom_name:
            new_name = base64.b64encode(bytes(self.rom_name)).decode()
            multidata["connect_names"][new_name] = multidata["connect_names"][self.world.player_name[self.player]]

        if self.topology_present:
            world_names = [
            LocationName.lake_orangatanga_region,
            LocationName.kremwood_forest_region,
            LocationName.cotton_top_cove_region,
            LocationName.mekanos_region,
            LocationName.k3_region,
            LocationName.razor_ridge_region,
            LocationName.kaos_kore_region,
            LocationName.krematoa_region,
            ]
            er_hint_data = {}
            for world_index in range(len(world_names)):
                for level_index in range(5):
                    level_region = self.world.get_region(self.active_level_list[world_index * 5 + level_index], self.player)
                    for location in level_region.locations:
                        er_hint_data[location.address] = world_names[world_index]
            multidata['er_hint_data'][self.player] = er_hint_data

    def create_regions(self):
        location_table = setup_locations(self.world, self.player)
        create_regions(self.world, self.player, location_table)

    def create_item(self, name: str, force_non_progression=False) -> Item:
        data = item_table[name]

        if force_non_progression:
            classification = ItemClassification.filler
        elif data.progression:
            classification = ItemClassification.progression
        else:
            classification = ItemClassification.filler

        created_item = DKC3Item(name, classification, data.code, self.player)

        return created_item

    def set_rules(self):
        set_rules(self.world, self.player)
