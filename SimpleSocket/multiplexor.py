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
from .simplesocket import ClientObject, SimpleClient
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

def _find_client(*args, **kwargs):
    for arg in args:
        if isinstance(arg, ClientObject) or isinstance(arg, SimpleClient):
            return arg
    for key, value in kwargs.items():
        if isinstance(value, ClientObject) or isinstance(value, SimpleClient):
            return value
    return None

def handle_event(func=None, threaded=True, process=False):
    """
    Decorator for handling events in a threaded manner.
    Must pass a `SimpleClient` or `ClientObject` instance to the first parameter of the decorated function.

    threaded: Run a new thread based event
    process: Run a new multiprocessing based event
    """
    assert callable(func) or func is None
    def _decorator(func) -> Callable[..., ThreadedConnection]:
        @wraps(func)
        def _wrapper(*args, **kwargs) -> ThreadedConnection:
            client = _find_client(*args, **kwargs)
            if threaded:
                thread = ThreadedConnection(_client=client, func=func, args=args, kwargs=kwargs)
                thread.start()
            if process:
                ...
            return thread
        return _wrapper
    return _decorator(func) if callable(func) else _decorator

class ThreadedConnection(Thread):
    def __init__(self, _client: ClientObject, func, **arguments):
        """
        Threaded Connection handler. 
        Creates a new thread for the event loop.
        """
        if not isinstance(_client, ClientObject) and not isinstance(_client, SimpleClient):
            raise ValueError("The first parameter is not a valid Client type object")
        super().__init__()
        self._func = func
        self._args = arguments['args']
        self._kwargs = arguments['kwargs']
        self._client = _client
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
            self.future = self._func(*self._args, **self._kwargs)
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

    def close(self):
        """
        Closes the associated client on this thread event
        """
        self._client.close()

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