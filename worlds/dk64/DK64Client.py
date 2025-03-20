import ModuleUpdate

ModuleUpdate.update()

import Utils

if __name__ == "__main__":
    Utils.init_logging("DK64Context", exception_logger="Client")

import asyncio
import colorama
import time
import typing
from client.common import DK64MemoryMap, create_task_log_exception
from client.pj64 import PJ64Client
from client.items import item_ids, item_names_to_id
from client.check_flag_locations import location_flag_to_name, location_name_to_flag
from client.ap_check_ids import check_id_to_name, check_names_to_id

from CommonClient import CommonContext, get_base_parser, gui_enabled, logger, server_loop
from NetUtils import ClientStatus


class DK64Client:
    n64_client = PJ64Client()
    tracker = None
    game = None
    auth = None
    recvd_checks = []
    players = None
    stop_bizhawk_spam = False
    remaining_checks = []
    flag_lookup = None
    seed_started = False
    memory_pointer = None

    async def wait_for_pj64(self):
        clear_waiting_message = True
        if not self.stop_bizhawk_spam:
            logger.info("Waiting on connection to PJ64...")
            self.stop_bizhawk_spam = True

        while True:
            try:
                socket_connected = False
                valid_rom = self.n64_client.validate_rom(self.game, DK64MemoryMap.memory_pointer)
                if self.n64_client.socket is not None and not socket_connected:
                    logger.info("Connected to PJ64")
                    socket_connected = True
                while not valid_rom:
                    if self.n64_client.socket is not None and not socket_connected:
                        logger.info("Connected to PJ64")
                        socket_connected = True
                    if clear_waiting_message:
                        logger.info("Waiting on valid ROM...")
                        clear_waiting_message = False
                    await asyncio.sleep(1.0)
                    valid_rom = self.n64_client.validate_rom(self.game, DK64MemoryMap.memory_pointer)
                self.stop_bizhawk_spam = False
                logger.info("PJ64 Connected to ROM!")
                return
            except (BlockingIOError, TimeoutError, ConnectionResetError):
                await asyncio.sleep(1.0)
                pass

    async def reset_auth(self):
        if not self.memory_pointer:
            self.memory_pointer = self.n64_client.read_u32(DK64MemoryMap.memory_pointer)
        self.n64_client.write_u8(self.memory_pointer + DK64MemoryMap.connection, [0xFF])

    async def wait_and_init_tracker(self):
        await self.wait_for_game_ready()

    async def recved_item_from_ap(self, item_id, item_name, from_player, next_index):
        # Don't allow getting an item until you've got your first check
        if not self.started_file():
            return

        # Spin until we either:
        # get an exception from a bad read (emu shut down or reset)
        # beat the game
        # the client handles the last pending item
        status = self.safe_to_send()
        # while not (await self.is_victory()) and not status:
        #     time.sleep(0.1)
        #     print("CHECKING SAFE TO SEND")
        #     print(status)
        #     status = self.safe_to_send()
        while not status:
            await asyncio.sleep(0.1)
            status = self.safe_to_send()
        next_index += 1
        # Strip out special characters from item name
        stripped_item_name = "".join(e for e in item_name if str(e).isalnum() or str(e) == " ")
        stripped_player_name = "".join(e for e in from_player if str(e).isalnum() or str(e) == " ")
        self.n64_client.write_u8(self.memory_pointer + DK64MemoryMap.counter_offset, [next_index])
        self.n64_client.write_bytestring(self.memory_pointer + DK64MemoryMap.fed_string, f"{stripped_item_name}")
        self.n64_client.write_bytestring(self.memory_pointer + DK64MemoryMap.fed_subtitle, f"From {stripped_player_name}")
        if item_ids.get(item_id):
            if item_ids[item_id].get("flag_id", None) != None:
                self.setFlag(item_ids[item_id].get("flag_id"))
            elif item_ids[item_id].get("fed_id", None) != None:
                await self.writeFedData(item_ids[item_id].get("fed_id"))
            else:
                logger.warning(f"Item {item_name} has no flag or fed id")

    async def writeFedData(self, fed_item):
        current_fed_item = self.n64_client.read_u32(self.memory_pointer + DK64MemoryMap.arch_items)
        # If item is being processed, don't update
        while current_fed_item != 0:
            current_fed_item = self.n64_client.read_u32(self.memory_pointer + DK64MemoryMap.arch_items)
            await asyncio.sleep(0.1)
            if current_fed_item == 0:
                break
        self.n64_client.write_u8(self.memory_pointer + 0x7, [fed_item])

    def check_safe_gameplay(self):
        current_gamemode = self.n64_client.read_u8(DK64MemoryMap.CurrentGamemode)
        next_gamemode = self.n64_client.read_u8(DK64MemoryMap.NextGamemode)
        return current_gamemode in [6, 0xD] and next_gamemode in [6, 0xD]

    def safe_to_send(self):
        countdown_value = self.n64_client.read_u8(self.memory_pointer + DK64MemoryMap.safety_text_timer)
        return countdown_value == 0

    def _getShopStatus(self, p_type: int, p_value: int, p_kong: int) -> bool:
        if p_type == 0xFFFF:
            return False
        if p_value == 0:
            return False
        if p_kong > 4:
            p_kong = 0
        kong_base = 0x807FC950 + (p_kong * 0x5E)
        if p_type < 5:
            val = self.n64_client.read_u8(kong_base + p_type)
            if p_type in (1, 3):
                # Slam, Ammo Belt
                return val >= p_type
            else:
                return (val & (1 << (p_value - 1))) != 0
        else:
            return self.readFlag(p_value) != 0

    def _build_flag_lookup(self):
        """Cache flag mappings to avoid repeated reads."""
        self.flag_lookup = {}
        for flut_index in range(0x400):
            raw_flag = self.n64_client.read_u16(0x807E2EE0 + (4 * flut_index))
            if raw_flag == 0xFFFF:
                break
            target_flag = self.n64_client.read_u16(0x807E2EE0 + (4 * flut_index) + 2)
            self.flag_lookup[raw_flag] = target_flag

    def getMoveStatus(self, move_flag: int) -> bool:
        item_kong = (move_flag >> 12) & 7
        if item_kong > 4:
            item_kong = 0
        item_type = (move_flag >> 8) & 15
        if item_type == 7:
            return True
        item_index = move_flag & 0xFF
        address = 0x807FC950 + (0x5E * item_kong) + item_type
        value = self.n64_client.read_u8(address)
        offset = 0
        if item_index > 0:
            offset = item_index - 1
        return ((value >> offset) & 1) != 0

    def getCheckStatus(self, check_type, flag_index=None, shop_index=None, level_index=None, kong_index=None) -> bool:
        # shop_index: 0 = cranky, 1 = funky, 2 = candy, 3=bfi
        # flag_index: as expected
        if check_type == "shop":
            if shop_index == 3:
                header = 0x807FF6E8
            else:
                header = 0x807FF400 + (shop_index * 0xF0) + (kong_index * 0x30) + (level_index * 6)
            purchase_type = self.n64_client.read_u16(header + 0)
            purchase_value = self.n64_client.read_u16(header + 2)
            purchase_kong = self.n64_client.read_u8(header + 4)
            return self._getShopStatus(purchase_type, purchase_value, purchase_kong)
        else:
            if self.flag_lookup is None:
                self._build_flag_lookup()

            # Check if the flag exists in the lookup table
            if flag_index in self.flag_lookup:
                target_flag = self.flag_lookup[flag_index]
                if target_flag & 0x8000:
                    return self.getMoveStatus(target_flag)
                elif target_flag == 0xFFFE:
                    has_camera = self.readFlag(0x2FD) != 0
                    has_shockwave = self.readFlag(0x179) != 0
                    return has_camera and has_shockwave
                return self.readFlag(target_flag) != 0
            else:
                return self.readFlag(flag_index) != 0

    async def readChecks(self, cb):
        """Run checks in parallel using asyncio with optimized processing."""
        new_checks = []
        remove_checks = set()  # Collect items to remove after iteration

        level_map = {
            "Japes": 0, "Aztec": 1, "Factory": 2, "Galleon": 3,
            "Forest": 4, "Caves": 5, "Castle": 6, "Isles": 7
        }
        shop_map = {"Cranky": 0, "Funky": 1, "Candy": 2}
        kong_map = {"Donkey": 0, "Diddy": 1, "Lanky": 2, "Tiny": 3, "Chunky": 4}

        for id in self.remaining_checks[:]:  # Iterate over a copy to avoid modification issues
            name = check_id_to_name.get(id)
            if not name:
                continue

            # Check location_name_to_flag first
            check = location_name_to_flag.get(name)
            if check and self.getCheckStatus("location", check):
                new_checks.append(id)
                remove_checks.add(id)
                continue

            # Check item_ids for flag_id
            check = item_ids.get(id)
            if check:
                flag_id = check.get("flag_id")
                if flag_id and self.getCheckStatus("location", flag_id):
                    new_checks.append(id)
                    remove_checks.add(id)
                continue

            # Special case: "The Banana Fairy's Gift"
            if name == "The Banana Fairy's Gift" and self.getCheckStatus("shop", None, 3, None, None):
                new_checks.append(id)
                remove_checks.add(id)
                continue

            # Shop Check Processing (Three-word names)
            content = name.split(" ")
            if len(content) == 3:
                level_index = level_map.get(content[0])
                shop_index = shop_map.get(content[1])
                kong_index = kong_map.get(content[2])

                if None not in (level_index, shop_index, kong_index):
                    if self.getCheckStatus("shop", None, shop_index, level_index, kong_index):
                        new_checks.append(id)
                        remove_checks.add(id)

        # Remove processed checks while keeping the original list
        self.remaining_checks = [id for id in self.remaining_checks if id not in remove_checks]

        if new_checks:
            cb(new_checks)
        return True



    def started_file(self):
        # Checks to see if the file has been started
        if not self.seed_started:
            status = self.readFlag(0) == 1
            if status:
                self.seed_started = True
            return status
        return True

    should_reset_auth = False

    def setFlag(self, index: int) -> int:
        byte_index = index >> 3
        shift = index & 7
        offset = DK64MemoryMap.EEPROM + byte_index
        val = self.n64_client.read_u8(offset)
        self.n64_client.write_u8(offset, [val | (1 << shift)])
        return 1

    def readFlag(self, index: int) -> int:
        byte_index = index >> 3
        shift = index & 7
        offset = DK64MemoryMap.EEPROM + byte_index
        val = self.n64_client.read_u8(offset)
        return (val >> shift) & 1

    async def wait_for_game_ready(self):
        logger.info("Waiting on game to be in valid state...")
        while not self.check_safe_gameplay():
            if self.should_reset_auth:
                self.should_reset_auth = False
                raise Exception("Resetting due to wrong archipelago server")
        logger.info("Game connection ready!")

    async def is_victory(self):
        return self.n64_client.read_u8(self.memory_pointer + DK64MemoryMap.end_credits) == 1

    def get_current_deliver_count(self):
        return self.n64_client.read_u8(self.memory_pointer + DK64MemoryMap.counter_offset)

    async def main_tick(self, item_get_cb, win_cb):
        await self.readChecks(item_get_cb)
        # await self.item_tracker.readItems()
        if await self.is_victory():
            await win_cb()

        current_deliver_count = self.get_current_deliver_count()

        if len(self.recvd_checks) > current_deliver_count:
            # Get the next item in recvd_checks
            item = self.recvd_checks[current_deliver_count]
            item_name = self.item_names.lookup_in_game(item.item)
            print(item_name)
            player_name = self.players.get(item.player)
            await self.recved_item_from_ap(item.item, item_name, player_name, current_deliver_count)


class DK64Context(CommonContext):
    tags = {"AP"}
    game = "Donkey Kong 64"
    la_task = None
    found_checks = []
    last_resend = time.time()
    remaining_checks = list(check_id_to_name.keys())

    won = False

    def __init__(self, server_address: typing.Optional[str], password: typing.Optional[str]) -> None:
        self.client = DK64Client()
        self.client.game = self.game.upper()
        self.client.remaining_checks = self.remaining_checks
        self.slot_data = {}

        super().__init__(server_address, password)

    def run_gui(self) -> None:
        from kvui import GameManager

        class DK64Manager(GameManager):
            logging_pairs = [
                ("Client", "Archipelago"),
                ("Tracker", "Tracker"),
            ]
            base_title = "Archipelago Donkey Kong 64 Client"

            def build(self):
                b = super().build()
                return b

        self.ui = DK64Manager(self)
        self.ui_task = asyncio.create_task(self.ui.async_run(), name="UI")

    async def send_checks(self):
        message = [{"cmd": "LocationChecks", "locations": self.found_checks}]
        await self.send_msgs(message)

    had_invalid_slot_data: typing.Optional[bool] = None

    def event_invalid_slot(self):
        # The next time we try to connect, reset the game loop for new auth
        self.had_invalid_slot_data = True
        self.auth = None
        # Don't try to autoreconnect, it will just fail
        self.disconnected_intentionally = True
        CommonContext.event_invalid_slot(self)

    async def send_victory(self):
        if not self.won:
            message = [{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}]
            logger.info("victory!")
            await self.send_msgs(message)
            self.won = True

    def new_checks(self, item_ids):
        self.found_checks += item_ids
        create_task_log_exception(self.send_checks())

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super(DK64Context, self).server_auth(password_requested)
        if self.had_invalid_slot_data:
            # We are connecting when previously we had the wrong ROM or server - just in case
            # re-read the ROM so that if the user had the correct address but wrong ROM, we
            # allow a successful reconnect
            self.client.should_reset_auth = True
            self.had_invalid_slot_data = False
        while self.client.auth == None:
            await asyncio.sleep(0.1)

            # # Just return if we're closing
            # if self.exit_event.is_set():
            #     return
            # Handler didn't set auth, ask user for slot name
            if self.client.auth is None:
                await self.get_username()
                break
        # self.auth = self.client.auth
        await self.send_connect()

    def on_package(self, cmd: str, args: dict):
        self.client.item_names = self.item_names
        if cmd == "Connected":
            self.game = self.slot_info[self.slot].game
            self.slot_data = args.get("slot_data", {})
            self.client.players = self.player_names

        if cmd == "ReceivedItems":
            for index, item in enumerate(args["items"], start=args["index"]):
                self.client.recvd_checks.append(item)

    async def sync(self):
        sync_msg = [{"cmd": "Sync"}]
        await self.send_msgs(sync_msg)

    async def run_game_loop(self):
        async def victory():
            await self.send_victory()

        def on_item_get(dk64_checks):
            # checks = [item_ids[check.id] for check in dk64_checks]
            built_checks_list = []
            for check in dk64_checks:
                check_name = check_id_to_name.get(check)
                if check_name:
                    built_checks_list.append(check)
                    continue
                item = item_ids.get(check)
                if item:
                    built_checks_list.append(check)
            self.new_checks(built_checks_list)

        # yield to allow UI to start
        await asyncio.sleep(0)
        while True:
            await asyncio.sleep(0.1)

            try:
                if not self.client.stop_bizhawk_spam:
                    logger.info("(Re)Starting game loop")
                self.found_checks.clear()
                # On restart of game loop, clear all checks, just in case we swapped ROMs
                # this isn't totally neccessary, but is extra safety against cross-ROM contamination
                self.client.recvd_checks.clear()
                await self.client.wait_for_pj64()
                await self.client.reset_auth()

                # If we find ourselves with new auth after the reset, reconnect
                if self.auth and self.client.auth != self.auth:
                    # It would be neat to reconnect here, but connection needs this loop to be running
                    logger.info("Detected new ROM, disconnecting...")
                    await self.disconnect()
                    continue
                if not self.client.recvd_checks:
                    await self.sync()

                # await self.client.wait_and_init_tracker()
                await asyncio.sleep(1.0)
                while True:
                    await self.client.reset_auth()
                    status = self.client.check_safe_gameplay()
                    if status == False:
                        await asyncio.sleep(5)
                        continue
                    await self.client.main_tick(on_item_get, victory)
                    await asyncio.sleep(1)
                    now = time.time()
                    if self.last_resend + 5.0 < now:
                        self.last_resend = now
                        await self.send_checks()
                    if self.client.should_reset_auth:
                        self.client.should_reset_auth = False
                        raise Exception("Resetting due to wrong archipelago server")
            except (asyncio.TimeoutError, TimeoutError, ConnectionResetError):
                await asyncio.sleep(1.0)


def launch():
    async def main():
        parser = get_base_parser(description="Donkey Kong 64 Client.")
        parser.add_argument("--url", help="Archipelago connection url")

        args = parser.parse_args()

        ctx = DK64Context(args.connect, args.password)
        ctx.items_handling = 0b101
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")

        ctx.la_task = create_task_log_exception(ctx.run_game_loop())
        if gui_enabled:
            ctx.run_gui()
        ctx.run_cli()

        await ctx.exit_event.wait()
        await ctx.shutdown()

    colorama.init()
    asyncio.run(main())
    colorama.deinit()


if __name__ == "__main__":
    launch()
