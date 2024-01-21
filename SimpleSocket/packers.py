from .constants import Constants
from .version import __version__
from .exceptions import decode_error
import base64
import json
import warnings
from loguru import logger
logging = logger.bind(name="SimpleSocket")

FORMAT = Constants.FORMAT
#socket API packers
def formatify(message:dict, padding: int = None):
    if padding:
        msg = json.dumps(message).ljust(padding)
        return msg.encode(FORMAT)
    return json.dumps(message).encode(FORMAT)

def decodify(message: bytes, padding: int = None):
    if padding:
        msg = message.decode(FORMAT)
        padding_end = msg.find('}', 0, padding)
        return json.loads(msg[:padding_end + 1])
    return json.loads(message.decode(FORMAT))

#Simple Socket packers
def pack_message(message, type_data):
        if not type_data:
            type_data = determine_type(message)
        if type_data == 'bytes':
            encoded_data = base64.b64encode(message)
        elif type_data == 'json':
            encoded_data = json.dumps(message)
        else:
            encoded_data = message
        initial_message = {
            "msg": encoded_data,
            "type": type_data,
            "version": __version__
        }
        encoded_message = json.dumps(initial_message).encode(encoding=FORMAT)
        return encoded_message

def unpack_message(data: bytes, suppress_errors = True):
    decoded_message = data.decode(encoding=FORMAT)
    try:
        unpacked_message = json.loads(decoded_message)
    except json.JSONDecodeError as e:
        logger.error("Incompatible message received! Error: %s" % e)
        return ""
    if unpacked_message.get('version') != __version__:
        raise TypeError(f"Version mismatch, the other line has: {__version__}")
    message = unpacked_message.get('msg')
    type_data = unpacked_message.get("type")
    try:
        if type_data == 'str':
            decoded_data = message
        elif type_data == 'int':
            decoded_data = int(message)
        elif type_data == 'bytes':
            decoded_data = base64.b64decode(message)
        elif type_data == 'json':
            decoded_data = json.loads(message)
    except (ValueError, json.decoder.JSONDecodeError) as e:
        if suppress_errors:
            warnings.warn("[Decode Error suppressed] Incorrect data type: {} and cannot be unpacked".format(type_data))
            return ""
        else: 
            raise decode_error("Incorrect data type: {} and cannot be unpacked".format(type_data))
    return decoded_data

def determine_type(data):
    if isinstance(data, bytes):
        return 'bytes'
    elif isinstance(data, int):
        return 'int'
    try:
        json.dumps(data)
        return 'json'
    except json.decoder.JSONDecodeError:
        # If decoding as JSON fails, assume it's a string
        return 'str'