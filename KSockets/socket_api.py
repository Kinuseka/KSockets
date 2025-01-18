"""
KSockets.socket_api
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
from . import options
from loguru import logger
import os

logging = logger.bind(name="SimpleSocket")
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
        """
        An API for sockets
        """
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
        Low level function, handling protocol incoming data,
        We should assume disconnection for invalid protocols
        """
        client_target = client if client else self.socket
        header_data = self._recvall(client_target, self.header_chunksize)
        if not header_data:
            logging.debug("Data received violates protocol, no header found")
            return False
        try:
            header = decodify(header_data, padding=self.header_chunksize)
            if not header: 
                logging.debug("Data received violates protocol, no is not decodable, this might be due to an error or a client is not following the protocol or outdated")
                return False
            total_len = header['a']
            chunked = header['r']
        except (KeyError, json.decoder.JSONDecodeError):
            logging.debug("Data received violates protocol, Message is not json decodable")
            return b''
        if chunked > self.chunk_size:
            logging.debug("Data received violates protocol, Chunked size is greater than the server's chunk size")
            return b''
            # return b''
        return self._receive_chunks(client_target, total_len)

    def _receive_chunks(self, client_target: socket.socket, total_len: int):
        "Receive packets in chunks"
        data = bytearray()
        remaining = total_len
        while remaining > 0:
            chunk_size = min(self.chunk_size, remaining)
            chunk = self._recvall(client_target, chunk_size)
            if not chunk:
                break  
            data.extend(chunk)
            remaining -= len(chunk)
        return bytes(data)
        
    def _recvall(self, client: socket.socket, byte_target):
        """
        Ensure we receive the exact amount of packets from TCP stream
        This ensures we prevent getting any extra or lacking data from the stream
        """
        data = bytearray()
        while len(data) < byte_target:
            packet = client.recv(byte_target - len(data))
            if not packet:
                return b''
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
        A client-side API for socket.
        Meant to bridge the functionality between SimpleSocket and Python sockets
        ~~~~
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
            self.iscustom = True
        else:
            self.iscustom = False

    def _create_connection(self):
        host, port = self.address
        err = None
        for res in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM):
            af, socktype, proto, canonname, sa = res
            try:
                self.socket = socket.socket(af, socktype, proto)
                # Break explicitly a reference cycle
                err = None
                return self.socket
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
        if not self.iscustom:
            self._create_connection()
        self.socket.connect(self.address)
        #{ch:16892}
        try:
            self.socket.sendall(formatify({'req': 'request-head'}, padding=1024))
            _raw_header = self.socket.recv(1024)
            _initial_header = decodify(_raw_header, padding=1024).get('ch', None)
            #sc indicates server allows client suggestion
            if _initial_header == 'sc': 
                _packed_msg = json.dumps({'ch': self.header_chunksize})
                self.socket.sendall(_packed_msg.encode('utf-8'))
            elif isinstance(_initial_header, int):
                self.chunk_size = _initial_header
        except json.decoder.JSONDecodeError as e:
            raise client_protocol_mismatch("Client cannot decode server's initial response. The client might be outdated or the server is invalid", property=self)
        except KeyError as e:
            raise client_protocol_mismatch("Header is decoded but cannot find the proper Key. The module might be outdated, Err:{}".format(e), property=self)
        #Header Chunksize is equal to the length of chunksize
    
    def close(self):
        if self.socket:
            self.socket.close()
class SocketServer(SocketAPI):
    def __init__(self, socket_obj: socket.socket = None, address: tuple = ('127.0.0.1', 3010,), chunk_size = 1024, enforce_chunks = True, dualstack_options = options.DUALSTACK_DISABLED) -> None:
        '''
        A server-side API for sockets.
        Meant to bridge the functionality between SimpleSocket and Python sockets
        ~~~~
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
        self.dualstack_options = dualstack_options
        self.socket = socket_obj
        self._socket = None
        if self.socket:
            self.iscustom = True
        else:
            self.iscustom = False

    def _create_socket(self):
        #Following socket.create_server as a reference with modifications
        ipv6_only = False
        dualstack_set = False
        if not socket.has_dualstack_ipv6() and self.dualstack_options == options.DUALSTACK_ENABLED:   
            raise ValueError("dualstack_ipv6 not supported on this platform")
        #Determine option for the correct AF type:
        if self.dualstack_options == options.DUALSTACK_DISABLED:
            AF = socket.AF_INET
        elif self.dualstack_options == options.IPV6_ONLY:
            AF = socket.AF_INET6
            ipv6_only = True
        elif self.dualstack_options == options.DUALSTACK_ENABLED:
            dualstack_set = True
            AF = socket.AF_INET6
        if not self.iscustom:
            self.socket = socket.socket(AF, socket.SOCK_STREAM)
        if os.name not in ('nt', 'cygwin') and \
                hasattr(socket._socket, 'SO_REUSEADDR'):
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except socket.error:
                # Fail later on bind(), for platforms which may not
                # support this option.
                pass
        if socket.has_ipv6 and AF == socket.AF_INET6:
            if dualstack_set:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            elif hasattr(socket._socket, "IPV6_V6ONLY") and \
                    hasattr(socket._socket, "IPPROTO_IPV6") and ipv6_only:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            else:
                raise ValueError('Your machine does not support ipv6')
        return self.socket
    
    def initialize_socket(self, reuse_port = False):
        if not self.iscustom:
            self._create_socket()
        if reuse_port and not hasattr(socket._socket, "SO_REUSEPORT"):
            raise ValueError("SO_REUSEPORT not supported on this platform")
        elif reuse_port:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.socket.bind(self.address)

    def listen_connections(self, backlog = 128):
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
                client.close()
            except (socket.timeout, BlockingIOError, OSError, socket.error):
                time.sleep(0.5)
                continue

        
    def close(self):
        self.socket.close()