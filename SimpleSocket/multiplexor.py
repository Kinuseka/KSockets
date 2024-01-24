"""
SimpleSocket.multiplexor
~~~~~~~~~~~~~
Handles concurrent based connections
"""
from typing import Callable, List
from threading import Thread
import concurrent.futures
from functools import wraps
import time
from loguru import logger
from .simplesocket import ClientObject
logging = logger.bind(name="SimpleSocket")

def _thread_handler(command, *args, **kwargs):
    try:
        return command(*args, **kwargs)
    except Exception as e:
        logging.exception("An error occured during multiplexing: %s" % e)

def multi_send(clients: List[ClientObject], current_client: ClientObject, message):
    """
    Allows you to relay the message to multiple clients concurrently. 

    clients: Server List of active clients
    current_client: Should be your ClientObject instance if you do not want echo response to the client sender, otherwise set None.
    message: Data to be sent
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(_thread_handler, client.send, message) for client in clients if current_client != client]
    return [f.result() for f in futures]

def handle_event(func=None, threaded=True, process=False):
    """
    Decorator for handling events in a threaded manner.
    Must pass a client or server instance to the function.
    """
    assert callable(func) or func is None
    def _decorator(func) -> Callable[..., ThreadedConnection]:
        @wraps(func)
        def _wrapper(client, *args, **kwargs) -> ThreadedConnection:
            if threaded:
                thread = ThreadedConnection(client, func ,*args, **kwargs)
                thread.start()
            if process:
                ...
            return thread
        return _wrapper
    return _decorator(func) if callable(func) else _decorator

class ThreadedConnection(Thread):
    def __init__(self, client: ClientObject, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._client = client
        #
        self.daemon = True
        self.future = None
        self.result = None  
        self.exception = None

    def run(self):
        """
        Run the thread
        """
        try:
            self.future = self._func(self._client, *self._args, *self._kwargs)
        except KeyboardInterrupt:
            return
        except Exception as e:
            logging.exception("An error occured on daemon thread due to: %s" % e)
            self.exception = e

    def wait(self, timeout: int = None):
        """
        Wait until this thread is finished

        timeout: Set duration amount of waiting before returning None. If not set, it will wait indefinitely
        """
        try:
            return self._get_result(timeout=timeout)
        except TimeoutError:
            return None

    def get_client(self):
        """
        Returns associated client object
        """
        return self._client

    def _get_result(self, timeout = None):
        if timeout:
            for i in range(timeout):
                if self.future:
                    return self.future
                time.sleep(1)
        else:
            self.join()
        return self.future