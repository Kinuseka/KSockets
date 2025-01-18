"""
KSockets.simplesocket
~~~~~~~~~~~~~
SimpleSocket for simple socket communication
"""
from threading import Thread
from typing import List, Union, TYPE_CHECKING
import socket
import json
import time
from uuid import uuid4
from loguru import logger
from .packers import pack_message, unpack_message, send_command
from .socket_api import SocketClient, SocketServer
from .constants import Constants, CMD
from .version import __version__
from . import exceptions as Exceptions
logging = logger.bind(name="SimpleSocket")
if TYPE_CHECKING:
    from .secure import SecureSocketClient
class SimpleClient:
    """
    High level class for communicating to server
    """
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

    def send_bytes(self, data: bytes, **kwargs):
        "Send raw data bytes. This is a lower level implementation and should use `.send()` instead"
        return self.client.send_all(data=data, **kwargs)

    def receive_bytes(self, **kwargs):
        "Receive raw data bytes. This is a lower level implementation and should use `.receive()` instead"
        data = self.client.receive_all(**kwargs)
        return data

    def connect(self):
        "Connect to the server"
        self.client.connect_to_server()
        self.send(Constants.ACKNOWLEDGE)
        if self.receive() == Constants.ACKNOWLEDGE:
            self.send(Constants.ASKID)
            self.id = int(self.receive()['ID'])
    
    def _reconnect(self, socket_api: Union["SecureSocketClient", SocketClient] = None):
        "Use `SimpleSocket.tools.reconnect_client to use the reconnect feature"
        self.client = socket_api
        self.client.connect_to_server()
        if self.receive() == Constants.ACKNOWLEDGE:
            resp = send_command(is_connected=bool(self.id), client=self.client, cmd=CMD.REQ_RECCON)
            if resp == CMD.REPL_RECCON_DE:
                raise Exceptions.ReconnectionFailure('Server Denied reconnection', property=self)
            elif resp == CMD.REPL_RECCON_OK:
                return True
    
    def send(self, data, type_data=None, thread_lock = True):
        """
        Send data to server
        data: data to be sent
        type: type of data to be sent, DEFAULT: None (int, bytes) if none then it will determine the type of data automatically
        thread_lock: make operation thread safe
        """
        message = pack_message(data, type_data=type_data)
        try:
            return self.send_bytes(data=message, thread_lock=thread_lock)
        except OSError as e:
            logging.warning("Could not send message due to: %s" % e)
            self.close()
            return 0

    def receive(self, timeout: int = 0, close_on_timeout = False, thread_lock = True, unpack_exc_detailed = False):
        """
        Receive data from the server
        timeout: How long to wait before unblocking. Set 0 for indefinite wait
        close_on_timeout: Connection will close if timeout reached. If false will return None
        thread_lock: make operation thread safe
        unpack_exc_detailed: Prints an exception if unpacking fails
        Returns None if connection is closed
        """
        limit = 1 if timeout == 0 else 0
        while limit != timeout:
            message = self.receive_bytes(thread_lock=thread_lock)
            if message:
                unpacked_message = unpack_message(message, suppress_errors=(not unpack_exc_detailed))
                if isinstance(unpacked_message, str) and (unpacked_message.find(Constants._OLD_PING_CODE) != -1 or unpacked_message.find(Constants.PING_CODE) != -1):
                    continue
                return unpacked_message
            elif isinstance(message, bool):
                self.close()
                break
            if timeout != 0:
                limit += 1
                time.sleep(1)
        else:
            if close_on_timeout:
                  self.close()
            return None

    def wait(self, thread):
        "Call this before running a thread"
        thread.start()
        time.sleep(1)

    def close(self):
        """
        Close the client
        """
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

class ClientObject:
    """
    Client object for connected clients
    """
    def __init__(self, parent: 'SimpleServer', client: socket.socket, address: list) -> None:
        self.client = client
        self.parent = parent
        self.address = address
        self.isactive = True
        self.id = 0

    def wait_for_reconnection(self, timeout = 15):
        "EXPERIMENTAL Wait until the client is reconnected"
        if self in self.parent.clients:
            return False
        self.parent.clients.append(self)
        for i in range(timeout):
            if self.isactive:
                break
            time.sleep(1)
        return bool(self.parent.find_client_by_id(self.id))
    
    def send_bytes(self, data: bytes, thread_lock = False):
        "Send raw data bytes. This is a lower level implementation and should use `.send()` instead"
        return self.parent._send_bytes(data=data, client=self.client, thread_lock=thread_lock)
    
    def receive_bytes(self, thread_lock = False):
        "Receive raw data bytes. This is a lower level implementation and should use `.receive()` instead"
        return self.parent._receive_bytes(client=self.client, thread_lock=thread_lock)

    def receive(self, timeout = 0, thread_lock = False):
        """
        Receive data from this client
        """
        try:
            message = self.parent.receive(client=self, timeout=timeout,thread_lock=thread_lock)
        except OSError as e:
            logging.warning("Could not receive message due to: %s" % e)
            self.close()
            return ""
        return message
    
    def send(self, data, type_data = None, thread_lock = False):
        """
        Send data to this client
        """
        try:
            return self.parent.send(data=data, type_data=type_data, client=self, thread_lock=thread_lock)
        except OSError as e:
            logging.warning("Could not send message due to: %s" % e)
            self.close()
            return 0

    def close(self):
        self.isactive = False
        try:
            self.client.close()
        except socket.error as e:
            logging.debug("Cannot close client due to error: %s" % e)
        try:
            if (self.parent.clients.index(self) + 1):
                self.parent.remove_client(client=self, fix_recursion=True)
        except ValueError:
            pass #We do nothing since its an expected error

class SimpleServer:
    """
    High level class for managing clients and accepting connections
    """
    def __init__(self, address = Constants.DEFAULT_ADDR, chunks = 4096, socket_api: SocketServer = None, ipv6_config = None):
        """
        address: Address to listen to.
        chunks: Size of the message chunk
        socket_api: High level socket object that inherits from `SocketAPI` class
        await_invalidation: Timeout to delete the client after 
        """
        self.address = address
        self.server = socket_api if socket_api else SocketServer(address=address, chunk_size = chunks)
        if ipv6_config:
            self.server.dualstack_options = ipv6_config
        self.version = __version__
        self.clients: List[ClientObject] = []
        self._secure = False

    #Transmit Backend
    def _send_bytes(self, data: bytes, client: socket.socket, **kwargs):
        return self.server.send_all(data=data, client=client, **kwargs)

    def _receive_bytes(self, client: socket.socket, **kwargs):
        return self.server.receive_all(client=client, **kwargs)
    
    #Transmission Line
    def send(self, data, client: ClientObject, type_data = None, thread_lock = False):
        """
        Send a data to a particular client
        """
        message = pack_message(data, type_data=type_data)
        return self._send_bytes(message, client=client.client, thread_lock=thread_lock)

    def receive(self, client: ClientObject, timeout: int = 0, thread_lock = False):
        """
        Receive data to a particular client
        """
        limit = 1 if timeout == 0 else 0
        while limit != timeout:
            message = self._receive_bytes(client=client.client, thread_lock=thread_lock)
            if message:
                unpacked_message = unpack_message(message)
                if isinstance(unpacked_message, str) and (unpacked_message.find(Constants._OLD_PING_CODE) != -1 or unpacked_message.find(Constants.PING_CODE) != -1):
                    continue
                elif isinstance(unpacked_message, str) and (unpacked_message.find(Constants.DISCONNECT) != -1):
                    self.remove_client(client)
                    break
                else:
                    return unpacked_message
            elif isinstance(message, bool):
                self.remove_client(client)
                break
            if timeout != 0:
                limit += 1
                time.sleep(1)
        else:
            self.remove_client(client)

    def close(self):
        "Closes the server"
        self.server.close()

    def create_server(self, reuse_port = False):
        "Creates a socket, and initializes it"
        self.server.initialize_socket(reuse_port=reuse_port)

    def listen(self, backlog: int = 128):
        "Start listening for incoming connections"
        if self.server.socket:
            self.server.listen_connections(backlog=backlog)
        else:
            raise Exceptions.NotReadyError('Server has not been properly initialized', property=self)
        
    def accept(self):
        "Handles automatic client accept, rejects incompatible clients, "
        if not self.server.socket:
            raise Exceptions.NotReadyError('Server has not been properly initialized', property=self)
        try:
            clientobj = ClientObject(self, *self.server.accept_client())
            message = clientobj.receive()
            if message.find(Constants.ACKNOWLEDGE) != -1:
                clientobj.send(Constants.ACKNOWLEDGE)
                clientresp = clientobj.receive()
                if clientresp.find(Constants._OLD_ASKID) != -1 or clientresp.find(Constants.ASKID) != -1:
                    gen_id = uuid4().int
                    clientobj.id = gen_id
                    clientobj.send({"ID": gen_id})
                elif clientresp.get('cmd') == CMD.REQ_RECCON:
                    #EXPERIMENTAL
                    client = self.find_client_by_id(clientresp.get('id'))
                    if not client:
                        return None
                    client.client = clientobj.client #Replace client backend
                    client.send(CMD.REPL_CHNK_OK)
                    client.isactive = True
                    return None
                self.clients.append(clientobj)
                return clientobj
            else:
                clientobj.close()
        except json.decoder.JSONDecodeError as e:
            return None

    def client_liveliness(self, clientobj: ClientObject):
        "Periodically sends a message to client to check if it is still live"
        def sleep_check(count):
            for i in range(count):
                if clientobj.isactive:
                    time.sleep(1)
                    continue
                else:
                    return False
            return True
        def checker():
            try:
                while True:
                    if sleep_check(30):
                        clientobj.send(Constants.PING_CODE.format(__version__))
                    else:
                        logger.info("Liveliness check stopped due to stopped client")
                        break
            except (ConnectionResetError, ConnectionAbortedError, ConnectionRefusedError, ConnectionError, json.decoder.JSONDecodeError, OSError) as e:
                logger.debug("Liveliness check failure due to: %s" % e)
                clientobj.isactive = False
                self.remove_client(clientobj)
        Thread(target=checker, daemon=True).start()

    def remove_client(self, client: ClientObject, fix_recursion=False):
        """
        Removes a specific client from the server
        """
        try:
            index = self.clients.index(client)
            clientobj = self.clients.pop(index)
            if not fix_recursion: clientobj.close()
        except (ValueError, IndexError) as e:
            logging.debug("Error suppressed when removing client: %s" % e)
            client.close()

    def remove_all_clients(self):
        """
        Removes all client connected to this server
        """

    def find_client_by_id(self, id) -> Union[None, ClientObject]:
        try:
            return next([client for client in self.clients if client.id == id])
        except TypeError:
            return None

    def __enter__(self):
        return self
    def __exit__(self, *args, **kwargs):
        self.close()
    