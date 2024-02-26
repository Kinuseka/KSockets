"""
SimpleSocket.model_api
~~~~~~~~~~~~~
Lower level api for socket communication
"""
from functools import wraps
import threading
import socket
import json
import time
from .exceptions import client_protocol_mismatch
from .constants import Constants as cnts
from .packers import formatify, decodify

rx_lock = threading.Lock()
tx_lock = threading.Lock()
def synchronized_tx(func):
    """
    Make transmitting thread safe
    """
    # Decorator to make the function thread-safe
    @wraps(func)
    def wrapper(*args, **kwargs):
        thread_lock = kwargs.get("thread_lock", None)
        if isinstance(thread_lock, bool) and thread_lock or thread_lock is None:
            with tx_lock:
                return func(*args, **kwargs)
        return func(*args, **kwargs)
    return wrapper
def synchronized_rx(func):
    """
    Make receiving thread safe
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        thread_lock = kwargs.get("thread_lock", None)
        if isinstance(thread_lock, bool) and thread_lock or thread_lock is None:
            with rx_lock:
                return func(*args, **kwargs)
        return func(*args, **kwargs)
    return wrapper

class SocketAPI:
    def __init__(self) -> None:
        self.chunk_size = None
        self.header_chunksize = None
        self.socket: socket.socket = None
    @synchronized_tx
    def send_all(self, data, client: socket.socket = None, **kwargs):
        """
        Low level function, handling protocol transmission
        """
        client_target = client if client else self.socket
        template = {
            'a': len(data),
            'r': self.chunk_size
        }
        if len(data) > self.chunk_size:
            client_target.sendall(formatify(template, padding=self.header_chunksize))
            chunks = [data[i:i+self.chunk_size] for i in range(0, len(data), self.chunk_size)]
            for chunk in chunks:
                client_target.sendall(chunk)
        else:
            template['r'] = len(data)
            client_target.sendall(formatify(template, padding=self.header_chunksize))
            client_target.sendall(data)
        return len(data)
    @synchronized_rx
    def receive_all(self, client: socket.socket = None, **kwargs):
        """
        Low level function, handling protocol incoming data
        """
        client_target = client if client else self.socket
        received_bytes = self._recvall(client_target, self.header_chunksize)
        if not received_bytes:
            return False
        try:
            header = decodify(received_bytes, padding=self.header_chunksize)
            total_len = header['a']
            chunked = header['r']
        except (KeyError, json.decoder.JSONDecodeError):
            return b''
        total_received = 0
        if not chunked > self.chunk_size:
            #Reject message if client disrespects negotiated chunk size
            data = b''
            data_left = total_len
            while not total_received >= total_len:
                if data_left > self.chunk_size:
                    chunked = self.chunk_size
                    data_left -= self.chunk_size
                else:
                    chunked = data_left
                new_data = self._recvall(client_target, chunked)
                if not new_data:
                    break
                data += new_data
                total_received = len(data)
            return data
        else: 
            return b''
        
    def _recvall(self, client: socket.socket, byte_target):
        data = bytearray()
        while len(data) < byte_target:
            packet = client.recv(byte_target - len(data))
            if not packet:
                return None
            data.extend(packet)
        return data
    
    def _cmd(self, head: str, body:str, client: socket.socket = None):
            cmd = head+" "+body
            body = cmd.ljust(cnts.HELLO_BUFF).encode(cnts.HELLO_FORM)
            _comm = client if client else self.socket
            _comm.send(body)
            _data = _comm.recv(cnts.HELLO_BUFF).decode(cnts.HELLO_FORM)

class SocketClient(SocketAPI):
    def __init__(self, socket_obj: socket.socket = None, address: tuple = None, chunk_size = 1024) -> None:
        '''
        socket: Socket object or socket class
        address: Destination address to connect to
        '''
        super().__init__()
        self.address = address
        self.chunk_size = chunk_size # Suggested chunksize but server might enforce a preferred one
        self.header_chunksize = cnts.HEADER_CHUNKS
        #Init Socket
        self.socket = socket_obj 
        self._socket = None
        if self.socket:
            self.socket = socket_obj
        else:
            self._socket = socket.socket

    def _create_connection(self):
        host, port = self.address
        err = None
        for res in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM):
            af, socktype, proto, canonname, sa = res
            try:
                self.socket = self._socket(af, socktype, proto)
                self.socket.connect(sa)
                # Break explicitly a reference cycle
                err = None
                return
            except OSError as _:
                err = _
                if self.socket is not None:
                    self.socket.close()
        if err is not None:
            try:
                raise err
            finally:
                # Break explicitly a reference cycle
                err = None
        else:
            raise OSError("getaddrinfo returns an empty list")


    def hello(self):
        ...

    def connect_to_server(self):
        if self._socket:
            self._create_connection()
        else:
            self.socket.connect()
        #{ch:16892}
        try:
            self.socket.sendall(formatify({'req': 'request-head'}, padding=1024))
            _initial_header = decodify(self.socket.recv(1024), padding=1024)['ch']
            #sc indicates server allows client suggestion
            if _initial_header == 'sc': 
                _packed_msg = json.dumps({'ch': self.header_chunksize})
                self.socket.sendall(_packed_msg.encode('utf-8'))
            else:
                self.chunk_size = _initial_header
        except json.decoder.JSONDecodeError as e:
            raise client_protocol_mismatch("Client cannot decode server's initial response. The client might be outdated or the server is invalid", property=self)
        except KeyError as e:
            raise client_protocol_mismatch("Header is decoded but cannot find the proper Key. The module might be outdated, Err:{}".format(e), property=self)
        #Header Chunksize is equal to the length of chunksize
    
    def close(self):
        self.socket.close()
        
class SocketServer(SocketAPI):
    def __init__(self, socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM), address: tuple = ('127.0.0.1', 3010), chunk_size = 1024, enforce_chunks = True) -> None:
        '''
        socket: Socket object
        address: Address to bind to
        chunk_size: Size of the message chunks
        enforce_chunks: Force clients to use your chunk_size option [Recommended: True]
        '''
        super().__init__()
        self.address = address
        self.chunk_size = chunk_size
        self.enforce_chunks = enforce_chunks
        self.header_chunksize = cnts.HEADER_CHUNKS
        self.socket = socket
        #Initialize server
        self.socket.bind(self.address)

    def listen_connections(self, backlog = 5):
        self.socket.listen(backlog)
    
    def hello_ack(self):
        ...
    
    def accept_client(self):
        """
        Accept connection and allow only after protocol has been enforced
        """
        while True:
            self.socket.setblocking(False)
            try:
                client, address = self.socket.accept()
                self.socket.setblocking(True)
                client.setblocking(True)
                request = decodify(client.recv(1024), padding=1024)
                if request.get("req") == "request-head":
                    client.sendall(formatify({'ch': self.chunk_size}, padding=1024))
                    return (client, address) 
            except (socket.timeout, BlockingIOError, OSError):
                time.sleep(0.5)
                continue      
        
    def close(self):
        self.socket.close()