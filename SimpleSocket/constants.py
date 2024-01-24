"""
SimpleSocket.constants
~~~~~~~~~~~~~
Stored constant variables
"""
class Constants:
    #General
    DEFAULT_ADDR = ('127.0.0.1', 3001)
    #Backend constants
    FORMAT = "utf-8"
    HEADER_CHUNKS = 128
    #Simple Client
    PING_CODE = "ms_SimpleSocketPing_version{}"
    DISCONNECT = "ms_SimpleSocketDisconnect_version{}"