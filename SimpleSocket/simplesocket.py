"""
SimpleSocket.simplesocket
~~~~~~~~~~~~~
SimpleSocket for simple socket communication
"""
from threading import Thread
from typing import List
import socket
import json
import time
from uuid import uuid4
from loguru import logger
from .packers import pack_message, unpack_message
from .model_api import Client_Main, Server_Main
from .constants import Constants
from .version import __version__
logging = logger.bind(name="SimpleSocket")

class SimpleClient:
    """
    High level class for communicating to server
    """
    def __init__(self, address = Constants.DEFAULT_ADDR) -> None:
        self.client = Client_Main(address=address)
        self.version = __version__
        self.clients = []
        self.id = 0

    def _send_bytes(self, data: bytes, **kwargs):
        return self.client.send(data=data, **kwargs)

    def _receive_bytes(self, **kwargs):
        data = self.client.receive(**kwargs)
        return data

    def connect(self):
        "Connect to the server"
        self.send(Constants.ACKNOWLEDGE)
        if self.receive() == Constants.ACKNOWLEDGE:
            self.send(Constants.ASKID)
            self.id = int(self.receive()['ID'])

    def send(self, data, type_data=None, thread_lock = True):
        """
        Send data to server
        data: data to be sent
        type: type of data to be sent, DEFAULT: None (int, bytes) if none then it will determine the type of data automatically
        thread_lock: make operation thread safe
        """
        message = pack_message(data, type_data=type_data)
        try:
            return self._send_bytes(data=message, thread_lock=thread_lock)
        except OSError as e:
            logging.warning("Could not send message due to: %s" % e)
            self.close()
            return 0

    def receive(self, timeout: int = 0, close_on_timeout = False, thread_lock = True):
        """
        Receive data from the server
        timeout: How long to wait before unblocking. Set 0 for indefinite wait
        close_on_timeout: Connection will close if timeout reached. If false will return None
        thread_lock: make operation thread safe
        """
        limit = 1 if timeout == 0 else 0
        while limit != timeout:
            message = self._receive_bytes(thread_lock=thread_lock)
            if message:
                unpacked_message = unpack_message(message)
                if unpacked_message == Constants.PING_CODE.format(__version__):
                    continue
                elif message == Constants.DISCONNECT.format(__version__):
                    self.close()
                    break
                else:
                    return unpacked_message
            elif isinstance(message, bool):
                self.close(already_dead=True)
                break
            if timeout != 0:
                limit += 1
                time.sleep(1)
        else:
            if close_on_timeout:
                self.close(already_dead=True)
            return None

    def wait(self, thread):
        "Call this before running a thread"
        thread.start()
        time.sleep(1)

    def close(self, already_dead = False):
        """
        Close the client
        """
        try:
            if not already_dead:
                self.send(Constants.DISCONNECT.format(__version__))
        except OSError as e:
            logging.debug("Failed to send disconnect notice due to: %s" % e)
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

class ClientObject:
    """
    Client object for connected clients
    """
    def __init__(self, parent: 'SimpleServer', client: socket.socket, address) -> None:
        self.client = client
        self.parent = parent
        self.address = address
        self.isactive = True
        self.id = 0

    def receive(self, timeout = 0,  thread_lock = False):
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

    def send(self, data, thread_lock = False):
        """
        Send data to this client
        """
        try:
            return self.parent.send(data=data, client=self, thread_lock=thread_lock)
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
    def __init__(self, address = Constants.DEFAULT_ADDR, chunks = 1024):
        self.server = Server_Main(address=address, chunk_size = chunks)
        self.version = __version__
        self.clients: List[ClientObject] = []
    #Transmit Backend
    def _send_bytes(self, data: bytes, client: socket.socket, **kwargs):
        return self.server.send(data=data, client=client, **kwargs)

    def _receive_bytes(self, client: socket.socket, **kwargs):
        return self.server.receive(client=client, **kwargs)
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
                if unpacked_message == Constants.PING_CODE.format(__version__):
                    continue
                elif message == Constants.DISCONNECT.format(__version__):
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

    def listen(self):
        "Start listening"
        self.server.listen()

    def accept(self):
        "Handles automatic client accept, rejects incompatible clients"
        clientobj = ClientObject(self, *self.server.accept())
        message = clientobj.receive()
        if message == "HelloAck":
            clientobj.send("HelloAck")
            if clientobj.receive() == Constants.ASKID:
                gen_id = uuid4().int
                clientobj.id = gen_id
                clientobj.send({"ID": gen_id})
            self.clients.append(clientobj)
            return clientobj
        else:
            clientobj.close()

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
            client.close(already_dead=True)

    def remove_all_clients(self):
        """
        Removes all client connected to this server
        """

    def __enter__(self):
        return self
    def __exit__(self, *args, **kwargs):
        self.close()
    