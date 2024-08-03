"""
KSockets.constants
~~~~~~~~~~~~~
Stored constant variables
"""
class Constants:
    #General
    DEFAULT_ADDR = ('127.0.0.1', 3001)
    ACKNOWLEDGE = "HelloAck"
    ASKID = "ms_SimpleSocketID_version{}"
    #Backend constants
    FORMAT = "utf-8"
    HELLO_BUFF = 16 #9b command, 1b space, 6b attribute
    HELLO_FORM = 'ascii'
    HEADER_CHUNKS = 128
    #Simple Client
    PING_CODE = "ms_SimpleSocketPing_version{}"
    DISCONNECT = "ms_SimpleSocketDisconnect_version{}"

class CMD:
    #Anonymous Commands
    #6W,1S,9Reserved
    SET_CHNK = "STCHNK"
    REPL_CHNK_OK = "STCHNK OK"
    REPL_CHNK_DE = "STCHNK DE"
    REQ_RECCON = "REQ RECONN"
    REPL_RECCON_OK = "RECONN OK"
    REPL_RECCON_DE = "RECONN DE"
    