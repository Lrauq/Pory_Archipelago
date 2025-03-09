"""Contains the PJ64Client class for interacting with Project64."""

import socket
import json
from dk64.client.common import N64Exception


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
        self.address = address
        self.port = port
        self.socket = None
        self.connected_message = False
        self._connect()

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
            data = int(self.socket.recv(1024).decode())
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
            data = int(self.socket.recv(1024).decode())
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
            data = int(self.socket.recv(1024).decode())
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
            self.socket.send(f"write bytestring {address} {data}".encode())
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

    def validate_rom(self, name):
        """
        Validates the ROM by comparing its good name with the provided name.

        Args:
            name (str): The name to validate against the ROM's good name.

        Returns:
            bool: True if the ROM's good name matches the provided name, False otherwise.
        """
        rom_info = self.rominfo()
        if not rom_info:
            return False
        if rom_info.get("goodName", None) == str(name).upper():
            return True
        return False
