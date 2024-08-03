from .socket_api import SocketClient, SocketServer, SocketAPI
from .simplesocket import SimpleClient, SimpleServer
from .constants import Constants as cnts
from typing import Union, overload
from loguru import logger
import ssl
import socket
logging = logger.bind(name="SimpleSocket")

class SecureSocketClient(SocketClient):
    def __init__(self,
                 context: ssl.SSLContext = None,
                 addr: tuple = None,
                 certpath = None,
                 verify = True,
                 *args,
                 **kwargs
                ):
        """
        Creates a secure version of `SocketClient`.
        Initializes TLS/SSL connection to the server.
        """

        if not context:
            context = ssl.SSLContext(
                    protocol=ssl.PROTOCOL_TLS_CLIENT
                )
            if not certpath and not verify:
                logging.warning('You will be prone for MITM! No valid certificate was indicated and will not verify if the server is legitimate. Use this for testing only!')
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            elif not certpath:
                context.load_default_certs(purpose=ssl.Purpose.SERVER_AUTH)
        if certpath:
            context.load_verify_locations(
                cafile=certpath
            )
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
                 context: ssl.SSLContext = None,
                 addr: tuple = None,
                 certpath = None,
                 keypath = None,
                 verify = True,
                 *args,
                 **kwargs
                ):
        """
        Creates a secure version of `SocketServer`.
        Initializes TLS/SSL connection to the clients.
        """
        if not context:
            context = ssl.SSLContext(
                    protocol=ssl.PROTOCOL_TLS_SERVER
                )
            if not certpath and not verify:
                logging.warning('You will be prone for MITM! No valid certificate was indicated and will not verify if the client is legitimate. Use this for testing only!')
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            elif not certpath:
                context.load_default_certs(purpose=ssl.Purpose.CLIENT_AUTH)
        if certpath:
            context.load_cert_chain(
                certfile=certpath,
                keyfile=keypath
            )
        context.options &= ~ssl.OP_NO_SSLv3
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        #Convert to secure socket
        sock_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        secure_server = context.wrap_socket(sock=sock_server, server_side=True)
        sock_server.close()
        secure_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().__init__(socket_obj=secure_server, address=addr, *args, **kwargs)
        self.address = addr


@overload
def wrap_secure(ssocket: SimpleClient,
                certpath: str = None,
                context: ssl.SSLContext = None,
                verify: bool = True
        ) -> SimpleClient: ...
@overload
def wrap_secure(ssocket: SimpleServer,
                certpath: str = None,
                keypath: str = None,
                context: ssl.SSLContext = None,
                verify: bool = True
        ) -> SimpleServer: ...

def wrap_secure(
        ssocket: Union[SimpleClient, SimpleServer],
        certpath: str = None,
        keypath: str = None,
        context: ssl.SSLContext = None,
        verify: bool = True
) -> Union[SimpleClient, SimpleServer]:
        """
        Converts a SimpleServer/SimpleClient to use a secure connection backend.

        It is recommended to only use this for simple configuration without much modification to the lower level classes.
        """
        _inst_type = None
        addr = ssocket.address
        if isinstance(ssocket, SimpleClient):
            _inst_type = 'client'
            socket_api: SocketClient = getattr(ssocket, 'client', None)
            socket_api.close()
            obj_vars = vars(socket_api)
            obj_vars.pop('socket')
            obj_vars.pop('_socket')
            ssocket._injector_variables = {
                'context': context,
                'addr': addr,
                'certpath': certpath,
                'verify': verify
            }
            secure_api = SecureSocketClient(**ssocket._injector_variables)
            for key in obj_vars:
                setattr(secure_api, key, obj_vars[key])
            ssocket._secure = True
            ssocket.client = secure_api
        elif isinstance(ssocket, SimpleServer):
            _inst_type = 'server'
            socket_api: SocketServer = getattr(ssocket, 'server', None)
            socket_api.close()
            obj_vars = vars(socket_api)
            obj_vars.pop('socket')
            ssocket._injector_variables = {
                'context': context,
                'addr': addr,
                'certpath': certpath,
                'keypath': keypath,
                'verify': verify
            }
            secure_api = SecureSocketServer(**ssocket._injector_variables)
            for key in obj_vars:
                setattr(secure_api, key, obj_vars[key])
            ssocket._secure = True
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