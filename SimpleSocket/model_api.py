from .exceptions import client_protocol_mismatch
from .constants import Constants as cnts
from .packers import formatify, decodify
import socket
import json
import threading
import time

def synchronized(func):
    # Decorator to make the function thread-safe
    lock = threading.Lock()
    def wrapper(*args, **kwargs):
        with lock:
            return func(*args, **kwargs)
    return wrapper

class Client_Main:
    def __init__(self, socket: socket.socket = socket.socket(), address: tuple = None, chunk_size = 1024) -> None:
        '''
        socket: Socket object
        address: Destination address to connect to
        '''
        self.address = address
        self.data_chunksize = chunk_size # Suggested chunksize but server might enforce a preferred one
        self.header_chunksize = cnts.HEADER_CHUNKS
        #Init Socket
        self.socket = socket
        self.socket.connect(self.address)
        #{ch:16892}
        try:
            self.socket.sendall(formatify({'req': 'request-head'}, padding=1024))
            _initial_header = decodify(self.socket.recv(1024), padding=1024)['ch']
            #sc indicates server allows client suggestion
            if _initial_header == 'sc': 
                _packed_msg = json.dumps({'ch': self.header_chunksize})
                self.socket.sendall(_packed_msg.encode('utf-8'))
            else:
                self.data_chunksize = _initial_header
        except json.decoder.JSONDecodeError as e:
            raise client_protocol_mismatch("Client cannot decode server's initial response. The client might be outdated or the server is invalid", property=self)
        except KeyError as e:
            raise client_protocol_mismatch("Header is decoded but cannot find the proper Key. The module might be outdated, Err:{}".format(e), property=self)
        #Header Chunksize is equal to the length of chunksize

    #Functions
    @synchronized
    def send(self, data):
        """
        Low level function, handling protocol sends
        """
        template = {
            'a': len(data),
            'r': self.data_chunksize
        }
        if len(data) > self.data_chunksize:
            self.socket.sendall(formatify(template, padding=self.header_chunksize))
            chunks = [data[i:i+self.data_chunksize] for i in range(0, len(data), self.data_chunksize)]
            for chunk in chunks:
                self.socket.sendall(chunk)
        else:
            template['r'] = len(data)
            self.socket.sendall(formatify(template, padding=self.header_chunksize))
            self.socket.sendall(data)
    
    @synchronized
    def receive(self) -> bytes:
        # Receive the header indicating the size of the chunk
        # Receive the chunk
        received_bytes = self.socket.recv(self.header_chunksize)
        if not received_bytes:
            return b''
        header = decodify(received_bytes, padding=self.header_chunksize)
        total_len = header['a']
        chunked = header['r']
        total_received = 0
        if not chunked > self.data_chunksize:
            #Reject message if server disrespects negotiated chunk size
            data = b''
            while total_received != total_len:
                if total_len > self.data_chunksize:
                    chunked = total_len - len(data)
                data += self.socket.recv(chunked)
                total_received += len(data)
            return data
        else:
            return b''
    
    def close(self):
        self.socket.close()
        

class Server_Main:
    def __init__(self, socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM), address: tuple = ('127.0.0.1', 3010), chunk_size = 1024, enforce_chunks = True) -> None:
        '''
        socket: Socket object
        address: Address to bind to
        chunk_size: Size of the message chunks
        enforce_chunks: Force clients to use your chunk_size option [Recommended: True]
        '''
        self.address = address
        self.chunk_size = chunk_size
        self.enforce_chunks = enforce_chunks
        self.header_chunksize = cnts.HEADER_CHUNKS
        self.socket = socket
        #Initialize server
        self.socket.bind(self.address)

    def listen(self, backlog = 5):
        self.socket.listen(backlog)
    
    def accept(self):
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
            except (socket.timeout, BlockingIOError, OSError) as e:
                time.sleep(0.5)
                continue      
    
    def send(self, data: bytes, client: socket.socket):
        """
        Low level function, handling protocol sends
        """
        template = {
            'a': len(data),
            'r': self.chunk_size
        }
        if len(data) > self.chunk_size:
            client.sendall(formatify(template, padding=self.header_chunksize))
            chunks = [data[i:i+self.chunk_size] for i in range(0, len(data), self.chunk_size)]
            for chunk in chunks:
                client.sendall(chunk)
        else:
            template['r'] = len(data)
            client.sendall(formatify(template, padding=self.header_chunksize))
            client.sendall(data)

    def receive(self, client: socket.socket):
        received_bytes = client.recv(self.header_chunksize)
        if not received_bytes:
            return b''
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
            while not total_received >= total_len:
                if total_len > self.chunk_size:
                    chunked = total_len - len(data)
                new_data = client.recv(chunked)
                if not new_data:
                    break
                data += new_data
                total_received = len(data)
            return data
        else: 
            return b''
    
    def close(self):
        self.socket.close()