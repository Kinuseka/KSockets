"""
SimpleSocket
~~~~~~~~~~~~~
Making Sockets simplier to implement
"""

from .simplesocket import SimpleClient, SimpleServer, ClientObject
from .constants import Constants
#
import sys
from loguru import logger
logger.remove()
logging = logger.bind(name="SimpleSocket")
logging.add(sys.stdout, colorize=True, format="<green>[SimpleSocket]</green><yellow>{time}</yellow> <level>{message}</level>")