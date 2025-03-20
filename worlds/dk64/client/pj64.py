"""Contains the PJ64Client class for interacting with Project64."""

import socket
import psutil
import json
import os
from configparser import ConfigParser
from Utils import open_filename
from Utils import get_settings


class N64Exception(Exception):
    """
    Custom exception class for N64-related errors.

    This exception is raised when an error specific to N64 operations occurs.

    Attributes:
        message (str): Explanation of the error.
    """

    pass


class PJ64Client:
    """
    PJ64Client is a class that provides an interface to connect to and interact with an N64 emulator.
    """

    def __init__(self, address="127.0.0.1", port=1337):
        """
        Initializes a new instance of the class.

        Args:
            address (str): The IP address to connect to. Defaults to "127.0.0.1".
            port (int): The port number to connect to. Defaults to 1337.
        """
        self._check_client()
        self.address = address
        self.port = port
        self.socket = None
        self.connected_message = False
        self._connect()

    def _check_client(self):
        """Ensures the Project 64 executable and the required adapter script are properly set up.

        Raises:
            N64Exception: If the Project 64 executable is not found or if the `ap_adapter.js` file is in use.
        """
        options = get_settings()
        executable = options.get("project64_options", {}).get("executable")
        if not executable:
            executable = open_filename("Project 64 4.0 Executable", (("Project64 Executable", (".exe",)),), "Project64.exe")
            if not executable:
                raise N64Exception("Project 64 executable not found.")
            options.update({"project64_options": {"executable": executable}})
            options.save()

        # Check if the file ap_adapter exists in the subfolder of the executable, the folder Scripts
        # If it does not exist, copy it from worlds/dk64/client/adapter.js
        adapter_path = os.path.join(os.path.dirname(executable), "Scripts", "ap_adapter.js")
        # Read the existing file from the world
        with open("worlds/dk64/client/adapter.js", "r") as f:
            adapter_content = f.read()
        # Check if the file is in use
        matching_content = False
        # Check if the contents match
        try:
            with open(adapter_path, "r") as f:
                if f.read() == adapter_content:
                    matching_content = True
        except FileNotFoundError:
            pass
        if not matching_content:
            try:
                with open(adapter_path, "w") as f:
                    f.write(adapter_content)
            except PermissionError:
                raise N64Exception("Unable to add adapter file to Project64, you may need to run this script as an administrator or close Project64.")
        self._verify_pj64_config(os.path.join(os.path.dirname(executable), "Config", "Project64.cfg"))
        # Check if project 64 is running
        if not self._is_exe_running(os.path.basename(executable)):
            # Run project 64
            os.popen(f'"{executable}"')

    def _is_exe_running(self, exe_name):
        """Check if a given executable is running."""
        for process in psutil.process_iter(['name']):
            if process.info['name'] and process.info['name'].lower() == exe_name.lower():
                return True
        return False

    def _verify_pj64_config(self, config_file):
        """Verifies and updates the configuration file for Project64.
        This method ensures that the specified configuration file contains the
        required sections and settings for proper operation. If the necessary
        sections or settings are missing, they are added or updated accordingly.
        Args:
            config_file (str): The path to the configuration file to be verified and updated.
        Behavior:
            - Ensures the [Settings] section exists and sets 'Basic Mode' to "0".
            - Ensures the [Debugger] section exists and sets 'Debugger' to "1".
            - Writes the updated configuration back to the file.
        Note:
            If an exception occurs while writing to the file, it is silently ignored.
        """
        # Read the CFG file
        config = ConfigParser()
        config.read(config_file)

        # Ensure the [Settings] section exists and update 'Basic Mode'
        if "Settings" not in config:
            config.add_section("Settings")
        config.set("Settings", "Basic Mode", "0")

        # Ensure the [Debugger] section exists and set 'Debugger'
        if "Debugger" not in config:
            config.add_section("Debugger")
        config.set("Debugger", "Debugger", "1")

        # Write the updated settings back to the file
        try:
            with open(config_file, "w") as configfile:
                config.write(configfile, space_around_delimiters=False)
        except Exception:
            pass

    def _connect(self):
        """
        Establishes a connection to the specified address and port using a socket.
        If the socket is not already created, it initializes a new socket with
        AF_INET and SOCK_STREAM parameters and sets a timeout of 0.1 seconds.
        Raises:
            N64Exception: If the connection is refused, reset, or aborted.
            OSError: If the socket is already connected.
        """

        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(0.1)
        try:
            self.socket.connect((self.address, self.port))
        except (ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError):
            self.socket = None
            raise N64Exception("Connection refused or reset")
        except OSError:
            # We're already connected, just move on
            pass

    def rominfo(self):
        """
        Retrieves ROM information from the connected N64 emulator.

        This method connects to the N64 emulator, sends a request for ROM information,
        and returns the received data as a dictionary.

        Returns:
            dict: A dictionary containing the ROM information.

        Raises:
            N64Exception: If the connection is refused, reset, or aborted.
        """
        try:
            self._connect()
            self.socket.send("romInfo".encode())
            data = self.socket.recv(1024).decode()
            return json.loads(data)
        except (ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError):
            raise N64Exception("Connection refused or reset")

    def read_u8(self, address):
        """
        Reads an 8-bit unsigned integer from the specified memory address.

        Args:
            address (int): The memory address to read from.

        Returns:
            int: The 8-bit unsigned integer read from the specified address.

        Raises:
            N64Exception: If the connection is refused, reset, or aborted.
        """
        try:
            self._connect()
            address = hex(address)
            self.socket.send(f"read u8 {address} 1".encode())
            server_response = self.socket.recv(1024).decode()
            if not server_response:
                raise N64Exception("No data received from the server")
            data = int(server_response)
            return data
        except (ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError):
            raise N64Exception("Connection refused or reset")

    def read_u16(self, address):
        """
        Reads a 16-bit unsigned integer from the specified memory address.

        Args:
            address (int): The memory address to read from.

        Returns:
            int: The 16-bit unsigned integer read from the specified address.

        Raises:
            N64Exception: If the connection is refused, reset, or aborted.
        """
        try:
            self._connect()
            address = hex(address)
            self.socket.send(f"read u16 {address} 2".encode())
            server_response = self.socket.recv(1024).decode()
            if not server_response:
                raise N64Exception("No data received from the server")
            data = int(server_response)
            return data
        except (ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError):
            raise N64Exception("Connection refused or reset")

    def read_u32(self, address):
        """
        Reads a 32-bit unsigned integer from the specified memory address.

        Args:
            address (int): The memory address to read from.

        Returns:
            int: The 32-bit unsigned integer read from the specified address.

        Raises:
            N64Exception: If the connection is refused, reset, or aborted.
        """
        try:
            self._connect()
            address = hex(address)
            self.socket.send(f"read u32 {address} 4".encode())
            server_response = self.socket.recv(1024).decode()
            if not server_response:
                raise N64Exception("No data received from the server")
            data = int(server_response)
            return data
        except (ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError):
            raise N64Exception("Connection refused or reset")

    def write_u8(self, address, data):
        """
        Writes an 8-bit unsigned integer to a specified address in the N64 emulator's memory.

        Args:
            address (int): The memory address to write to.
            data (int): The 8-bit unsigned integer data to write.

        Returns:
            str: The response from the emulator after the write operation.

        Raises:
            N64Exception: If the connection to the emulator is refused, reset, or aborted.
        """
        try:
            self._connect()
            address = hex(address)
            self.socket.send(f"write u8 {address} {data}".encode())
            data = self.socket.recv(1024).decode()
            return data
        except (ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError):
            raise N64Exception("Connection refused or reset")

    def write_bytestring(self, address, data):
        """
        Writes a bytestring to a specified address on the connected N64 device.

        Args:
            address (int): The memory address to write the bytestring to.
            data (str): The bytestring data to write.

        Returns:
            str: The response from the N64 device after writing the bytestring.

        Raises:
            N64Exception: If the connection is refused, reset, or aborted.
        """
        try:
            self._connect()
            address = hex(address)
            data = str(data).upper()
            self.socket.send(f"write bytestring {address} {data}\x00".encode())
            data = self.socket.recv(1024).decode()
            return data
        except (ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError):
            raise N64Exception("Connection refused or reset")

    def write_u32(self, address, data):
        """
        Writes a 32-bit unsigned integer to the specified address in the N64 emulator.

        Args:
            address (int): The memory address to write to.
            data (int): The 32-bit unsigned integer data to write.

        Returns:
            str: The response from the emulator after writing the data.

        Raises:
            N64Exception: If the connection to the emulator is refused, reset, or aborted.
        """
        try:
            self._connect()
            address = hex(address)
            self.socket.send(f"write u32 {address} {data}".encode())
            data = self.socket.recv(1024).decode()
            return data
        except (ConnectionRefusedError, ConnectionResetError, ConnectionAbortedError):
            raise N64Exception("Connection refused or reset")

    def validate_rom(self, name, memory_location=None):
        """
        Validates the ROM by comparing its good name with the provided name.

        Args:
            name (str): The name to validate against the ROM's good name.
            memory_location (int): The memory location to read from to verify the ROM is Archipelago.

        Returns:
            bool: True if the ROM's good name matches the provided name, False otherwise.
        """
        rom_info = self.rominfo()
        if not rom_info:
            return False
        if rom_info.get("goodName", None) == str(name).upper():
            if memory_location:
                memory_result = self.read_u32(memory_location)
                if memory_result != 0:
                    return True
                return False
            else:
                return True
        return False
