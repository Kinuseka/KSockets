from .packers import pack_message, unpack_message
from .model_api import Client_Main, Server_Main
from .constants import Constants
from .version import __version__
from threading import Thread
from typing import Union, Type, List
import socket
import json
import time
from loguru import logger
logging = logger.bind(name="SimpleSocket")

class SimpleClient: 
    """
    High level class for communicating to server
    """
    def __init__(self, address = Constants.DEFAULT_ADDR) -> None:
        self.client = Client_Main(address=address)
        self.version = __version__
        self.clients = []
        #Acknowledge Hello
        self.receive()
        self.send("HelloAck")

    def _send_bytes(self, data: bytes):
        return self.client.send(data=data)
    
    def _receive_bytes(self):
        data = self.client.receive()
        return data

    def send(self, data, type_data=None):
        """
        Send data to server
        data: data to be sent
        type: type of data to be sent, DEFAULT: None (int, bytes) if none then it will determine the type of data automatically
        """
        "Send message to connected server"
        message = pack_message(data, type_data=type_data)
        return self._send_bytes(message)
    
    def receive(self, timeout = 10):
        limit = 0
        while limit != timeout:
            message = self._receive_bytes()
            if message:
                unpacked_message = unpack_message(message)
                if unpacked_message == Constants.PING_CODE.format(__version__):
                    continue
                elif message == Constants.DISCONNECT.format(__version__):
                    self.close()
                    break
                else:
                    return unpacked_message
            limit += 1
        else:
           self.close(already_dead=True)
    
    def wait(self, thread):
        "Call this before running a thread"
        thread.start()
        time.sleep(1)
    
    def close(self, already_dead = False):
        if not already_dead:
            self.send(Constants.DISCONNECT.format(__version__))
        self.client.close()
        
    def __enter__(self):
        return self
    
    def __exit__(self, *args, **kwargs):
        self.close()

class ClientObject:
    "A seperate client object connected"
    def __init__(self, parent: 'SimpleServer', client: socket.socket, address) -> None:
        self.client = client
        self.parent = parent
        self.address = address
        self.isactive = True
    
    def receive(self):
        try:
            message = self.parent.receive(client=self)
        except OSError as e:
            logging.warning("Could not receive message due to: %s" % e)
            self.close(already_dead=True)
            return ""
        return message
    
    def send(self, message):
        try:
            return self.parent.send(data=message, client=self)
        except OSError as e:
            logging.warning("Could not send message due to: %s" % e)
            self.close(already_dead=True)
            
    def close(self, already_dead = False):
        "Disconnects this particular client"
        if not already_dead:
            try:
                self.parent.send(Constants.DISCONNECT.format(__version__), client=self)
            except socket.error as e:
                logging.debug("Cannot send disconnection message due to: %s" % e)
        self.isactive = False
        try:
            self.client.close()
        except socket.error as e:
            logging.debug("Cannot close client due to error: %s" % e)
        try:
            if (self.parent.clients.index(self) + 1):
                self.parent.remove_client(client=self, fix_recursion=True)
        except ValueError as e:
            pass #We do nothing since its an expected error

class SimpleServer:
    """
    High level class for managing clients
    """
    def __init__(self, address = Constants.DEFAULT_ADDR, chunks = 1024):
        self.server = Server_Main(address=address, chunk_size = chunks)
        self.version = __version__
        self.clients: List[ClientObject] = []

    #Transmit Backend
    def _send_bytes(self, data: bytes, client: socket.socket):
        "Send to lower class"
        return self.server.send(data=data, client=client)
    
    def _receive_bytes(self, client: socket.socket):
        return self.server.receive(client=client)
    #Transmission Line
    def send(self, data, client: ClientObject, type_data = None):
        message = pack_message(data, type_data=type_data)
        return self._send_bytes(message, client=client.client)
    
    def receive(self, client: ClientObject, timeout=10):
        limit = 0
        while limit != timeout:
            message = self._receive_bytes(client=client.client)
            if message:
                unpacked_message = unpack_message(message)
                if unpacked_message == Constants.PING_CODE.format(__version__):
                    continue
                elif message == Constants.DISCONNECT.format(__version__):
                    client.close()
                    self.remove_client(client)
                    break
                else:
                    return unpacked_message
            limit += 1
        else:
            client.close(already_dead=True)
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
        clientobj.send("HelloAck")
        clientobj.receive() #Await for client acknowledge
        self.clients.append(clientobj)
        return clientobj
    
    def client_liveliness(self, clientobj: ClientObject):
        "Periodically sends a message to client to check if it is still live"
        def checker():
            try:
                while True:
                    if clientobj.isactive:
                        time.sleep(30)
                        clientobj.send(Constants.PING_CODE.format(__version__))
                    else:
                        break
            except (ConnectionResetError, ConnectionAbortedError, ConnectionRefusedError, ConnectionError, json.decoder.JSONDecodeError, OSError):
                clientobj.isactive = False
                self.remove_client(clientobj)
        Thread(target=checker, daemon=True).start()
    
    def remove_client(self, client: ClientObject, fix_recursion=False):
        "Removes a client from the server"
        try:
            index = self.clients.index(client)
            clientobj = self.clients.pop(index)
            if not fix_recursion: clientobj.close()
        except (ValueError, IndexError) as e:
            logging.debug("Error suppressed when removing client: %s" % e)
            client.close(already_dead=True)

    def __enter__(self):
        return self
    def __exit__(self, *args, **kwargs):
        self.close()        