class SocketException(BaseException):
    "General Socket Exception"
    def __init__(self, message, property, *args, **kwargs):
        self.message=message
        self.property=property
        super().__init__(message,*args,**kwargs)
    
class client_protocol_mismatch(SocketException):
    "The server protocol does not follow the steps that the client knows"
    def __init__(self, message, property, *args, **kwargs):
        super().__init__(message, property, *args, **kwargs)

class decode_error(SocketException):
    "The message type is incorrect from what was declared"
    def __init__(self, message, property, *args, **kwargs):
        super().__init__(message, property, *args, **kwargs)
