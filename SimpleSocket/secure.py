from .socket_api import SocketClient, SocketServer, SocketAPI
from .simplesocket import SimpleClient, SimpleServer
from .constants import Constants as cnts
from typing import Union
import ssl
import socket

class SecureSocketClient(SocketClient):
    def __init__(self,
                 context: ssl.SSLContext,
                 addr: tuple = None,
                 *args,
                 **kwargs
                ):
        context = context if context else ssl.create_default_context()
        context.options &= ~ssl.OP_NO_SSLv3
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        #Convert to secure socket
        sock_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # sock_client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        secure_client = context.wrap_socket(sock=sock_client, server_hostname=addr[0])
        sock_client.close()
        super().__init__(socket_obj=secure_client, address=addr, *args, **kwargs)
        self.address = addr

class SecureSocketServer(SocketServer):
    def __init__(self,
                 context: ssl.SSLContext,
                 addr: tuple = None,
                 *args,
                 **kwargs
                ):
        context = context if context else ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.options &= ~ssl.OP_NO_SSLv3
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        #Convert to secure socket
        sock_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        secure_server = context.wrap_socket(sock=sock_server, server_side=True)
        sock_server.close()
        secure_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().__init__(socket_obj=secure_server, address=addr, *args, **kwargs)
        self.address = addr

def wrap_secure(
        ssocket: Union[SimpleServer, SimpleClient],
        context: ssl.SSLContext
):
        """
        Run Simple socket under secure TLS/SSL socket backend
        """
        _inst_type = None
        addr = ssocket.address
        if isinstance(ssocket, SimpleClient):
                _inst_type = 'client'
                socket_api: SocketClient = getattr(ssocket, 'client', None)
                socket_api.close()
                secure_api = SecureSocketClient(context=context, addr=addr)
                ssocket.client = secure_api
        elif isinstance(ssocket, SimpleServer):
                _inst_type = 'server'
                socket_api: SocketServer = getattr(ssocket, 'server', None)
                socket_api.close()
                secure_api = SecureSocketServer(context=context, addr=addr)
                ssocket.server = secure_api
        else:
                raise AttributeError('Invalid instance')
        return ssocket
# def simpleClientSSL(
#             socket_api: Union[SocketClient, SocketServer], 
#             context: ssl.SSLContext = None
#         ):
#     if isinstance(socket_api, SocketClient):
#         return Socket
