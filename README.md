# KSockets
Make sockets super simple!

## KSockets
KSockets is a super simple socket integration on python. It ensures reliable TCP communication without having to do many specific setups.

## Installation
`pip install KSockets`

## Usage

### Basic Client/Server Communication
Client:
```py
from KSockets import SimpleClient

client = SimpleClient(("127.0.0.1", 3001))
client.connect()

# Send data to server
client.send("Hello Server!")

# Receive data from server
response = client.receive()
print(f"Received: {response}")

# Close connection
client.close()
```

Server: 
```py
from KSockets import SimpleServer

server = SimpleServer(("127.0.0.1", 3001), chunks=8196)
server.create_server()
server.listen()

# Handle a client connection
client = server.accept()
print(f"Client connected: {client.address}")

# Receive data from client
data = client.receive()
print(f"Received: {data}")

# Send response
client.send("Hello Client!")

# Close server
server.close()
```

### Secure Communication
```py
from KSockets import SimpleClient, SimpleServer
from KSockets.secure import wrap_secure

# Create secure client
client = SimpleClient(("127.0.0.1", 3001))
secure_client = wrap_secure(client, certpath="path/to/cert.pem")
secure_client.connect()

# Create secure server
server = SimpleServer(("127.0.0.1", 3001))
secure_server = wrap_secure(server, certpath="path/to/cert.pem", keypath="path/to/key.pem")
secure_server.create_server()
secure_server.listen()
```

### Using Event Handling
```py
from KSockets import SimpleServer
from KSockets.multiplexor import handle_event

server = SimpleServer(("127.0.0.1", 3001))
server.create_server()
server.listen()

@handle_event
def handle_client(client):
    while True:
        data = client.receive()
        if not data:
            break
        print(f"Received: {data}")
        client.send(f"Echo: {data}")

# Start a new thread for each client
client = server.accept()
handle_client(client)  # This runs in a separate thread
```

### Broadcasting Messages
```py
from KSockets import SimpleServer
from KSockets.multiplexor import multi_send, handle_event

server = SimpleServer(("127.0.0.1", 3001))
server.create_server()
server.listen()

@handle_event
def handle_client(client):
    # Receive data from client
    while client.isalive:
        message = client.receive()
        if not message:
            break
            
        print(f"Client {client.id} says: {message}")
        
        # Broadcast the message to all OTHER clients
        # Example 1
        multi_send(server.clients, client, message) # Exclude the sender
        # Example 2
        multi_send(client.parent.clients, client, message) # ClientObject instance can still refer back to its parent which is the SimpleServer
        # Example 3
        multi_send(client.parent.clients, None, message) # Echo back the message to the sender

# Accept clients (server tracks them automatically)
while True:
    client = server.accept()
    if client:

        handle_client(client)
```

**Note:** In the above example:
- The `client` in `multi_send(server.clients, client, message)` is the sender client
- `multi_send` sends the message to all clients in the list EXCEPT the sender if specified (refer example 1 and 2)
- This prevents clients from receiving their own messages back

### Additional Features

#### Connection Liveliness
```py
from KSockets import SimpleServer
import time

server = SimpleServer(("127.0.0.1", 3001))
server.create_server()
server.listen()

client = server.accept()

# Check client connection status
server.client_liveliness(client)  # Starts background thread checking connection

# Find client by ID
client_id = client.id
client = server.find_client_by_id(client_id)
```

#### Context Manager Support
```py
# Using context manager for automatic resource cleanup
with SimpleServer(("127.0.0.1", 3001)) as server:
    server.create_server()
    server.listen()
    client = server.accept()
    client.send("Hello!")
    
with SimpleClient(("127.0.0.1", 3001)) as client:
    client.connect()
    client.send("Hello server!")
    response = client.receive()
```

## Support
Contact support@kinuseka.us for any queries
