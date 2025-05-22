from .constants import Constants, CMD
from .version import __version__

class SimpleUDPServer:
    def __init__(self, address = Constants.DEFAULT_ADDR, socket_api:SocketClient = None) -> None:
        """
        address = Address to connect to.
        socket_api: High level socket object that inherits from `SocketAPI` class
        """
        self.address = address
        self.version = __version__
        self.client = socket_api if socket_api else SocketClient(address=self.address)
        self.id = 0
        self._secure = False
        