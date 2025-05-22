"""
KSockets.packers
~~~~~~~~~~~~~
Decoding and encoding tools for packets
"""
import json
import base64
from typing import Union, TYPE_CHECKING
from loguru import logger
from semver import Version
from .constants import Constants
from .version import __version__, __version_semver__
from zstandard import ZstdCompressor, ZstdDecompressor
logging = logger.bind(name="SimpleSocket")

if TYPE_CHECKING:
    from .simplesocket import SimpleClient

FORMAT = Constants.FORMAT

class CompressionManager:
    def __init__(self, type: int, level:int):
        if type == 1:
            self.compressor = ZstdCompressor(level=level)
            self.decompressor = ZstdDecompressor()
        #Normally impossible to fail this area
    
    def compress(self, data: bytes):
        cmp_data = self.compressor.compress(data)
        return cmp_data
    
    def decompress(self, data: bytes):
        dec_data = self.decompressor.decompress(data)
        return dec_data

#socket API packers
def formatify(message: dict, padding: int = None):
    if padding:
        # encoded = json.dumps(message).encode(FORMAT)
        # pad_adjust = padding - len(message)
        # message = encoded + b' ' * pad_adjust
        # return message
        msg = json.dumps(message)
        msg = msg.ljust(padding)
        return msg.encode(FORMAT)
    return json.dumps(message).encode(FORMAT)

def decodify(message: bytes, padding: int = None):
    try:
        if padding:
            msg = message.decode(FORMAT)
            padding_end = msg.find('}', 0, padding)
            return json.loads(msg[:padding_end + 1])
        return json.loads(message.decode(FORMAT))
    except UnicodeDecodeError:
        return {}

#Simple Socket packers
def pack_message(message, type_data):
    if not type_data:
        type_data = determine_type(message)
    if type_data == 'bytes':
        encoded_data = base64.b64encode(message).decode('ascii')
    elif type_data == 'json':
        if isinstance(message, dict):
            encoded_data = json.dumps(message)
        else:
            logging.error("Received non-dict data type but type_data is %s: %s" % (type(message), type_data))
            return False
    else:
        encoded_data = message
    initial_message = {
        "msg": encoded_data,
        "type": type_data,
        "version": __version_semver__
    }
    encoded_message = json.dumps(initial_message).encode(encoding=FORMAT)
    return encoded_message

def unpack_message(data: bytes, suppress_errors = False) -> Union[str, int, dict, bytes]:
    decoded_message = data.decode(encoding=FORMAT)
    try:
        unpacked_message = json.loads(decoded_message)
    except json.JSONDecodeError as e:
        logger.error("Incompatible message received! Error: %s" % e)
        return ""
    try:
        version_remote = Version.parse(unpacked_message.get("version"))
        version_local = Version.parse(__version_semver__)
        if not version_remote.is_compatible(version_local): 
            #Check if remote is compatible with local. 
            #Example 1.1.0 should be compatible with 1.0.0
            #1.0.0.is_compatible(1.1.0) = True
            logger.error("Incompatible version received from server/client: %s" % version_remote)
            return ""
    except (ValueError):
        logging.error("An incompatible version was received from server/client")
        return ""
    try:
        message = unpacked_message.get('msg')
        type_data = unpacked_message.get("type")
        if type_data == 'str':
            decoded_data = message
        elif type_data == 'int':
            decoded_data = int(message)
        elif type_data == 'bytes':
            decoded_data = base64.b64decode(message)
        elif type_data == 'json':
            decoded_data = json.loads(message)
        else:
            if not suppress_errors:
                logging.error("Received unknown data type from client: %s" % type_data)
            return ""
    except (ValueError, json.decoder.JSONDecodeError):
        if suppress_errors:
            logging.warning("Incorrect data type: %s and cannot be unpacked" % type_data)
        else:
            logging.exception("Incorrect data type: %s and cannot be unpacked" % type_data)
        return ""
    return decoded_data

def determine_type(data):
    if isinstance(data, bytes):
        return 'bytes'
    elif isinstance(data, int):
        return 'int'
    elif isinstance(data, dict):
        return 'json'
    else:
        #Set default encoding to string
        return 'str'
    
def send_command(is_connected: bool, client: 'SimpleClient', cmd):
    if is_connected:
        msg = {'cmd': cmd, 'id': client.id}
    else:
        msg = {'cmd': cmd, 'id': 'anonymous'}
    client.send(msg, type_data='json')
    received = client.receive(timeout=15)
    return received