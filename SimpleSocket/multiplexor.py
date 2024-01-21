"""
SimpleSocket.multiplexor
~~~~~~~~~~~~~
Handles concurrent based connections
"""

from .simplesocket import ClientObject
from typing import Callable, List
import concurrent.futures
from loguru import logger
logging = logger.bind(name="SimpleSocket")

def _thread_handler(command, *args, **kwargs):
    try:
        return command(*args, **kwargs)
    except Exception as e:
        logging.exception("An error occured during multiplexing: %s" % e)

def multi_send(clients: List[ClientObject], current_client: ClientObject, message):
    "Sends to multiple connections at once"
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(_thread_handler, client.send, message) for client in clients if current_client != client]
    return [f.result() for f in futures]
