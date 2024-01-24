"""
SimpleSocket
~~~~~~~~~~~~~
Making Sockets simplier to implement
"""

from .simplesocket import SimpleClient, SimpleServer, ClientObject
from .model_api import Client_Main, Server_Main
from .constants import Constants
#
import sys
from loguru import logger
logger.remove()
logging = logger.bind(name="SimpleSocket")
logging.add(sys.stdout, colorize=True, format="<green>[SimpleSocket]</green><yellow>{time}</yellow> <level>{message}</level>")