from .secure import SecureSocketClient, SecureSocketServer
from .simplesocket import SocketClient
from .simplesocket import SimpleClient
from typing import Union
import time

def reconnect_client(client: Union[SimpleClient, SecureSocketClient], socket_client = None):
    """
    EXPERIMENTAL
    Handle Reconnection for client 
    """
    time.sleep(3)
    socket = socket_client if socket_client else SocketClient(address=client.address)
    if client._secure:
        _injector = client._injector_variables
        return client._reconnect(SecureSocketClient(**_injector))
    else:
        return client._reconnect(socket)